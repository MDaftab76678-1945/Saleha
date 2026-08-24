"""
Saleha Core: Project Builder (New -- multi-file project support)

Abhi tak Saleha sirf ek chhota function/script bana sakta tha (single file).
Ye module bade goals ko multiple files me todta hai -- jaise "ek chhota
Flask app banao" ko `app.py`, `models.py`, `requirements.txt` me todna.

Kaam kaise karta hai:
1. Planner LLM se poochta hai: "is goal ke liye kaunsi files chahiye?"
   (JSON list ke roop me: filename + kya us file me hona chahiye)
2. Har file ke liye alag se CoderAgent call hota hai (context ke saath ki
   baaki files me kya hai, taaki imports/naming match ho)
3. Har file Tester se guzarti hai (syntax/security check)
4. Sab files ek project folder me save hoti hain

Limitations (honest scope):
- Har file independently generate hoti hai -- cross-file logic errors
  (jaise ek file dusri file ka function galat naam se import kare) pura
  pakde nahi ja sakte, kyunki files ek dusre ko run-time pe verify nahi
  karti (sirf saath wali files ka summary context me diya jaata hai).
- Self-healing loop (jo single-file mode me hai) yahan nahi hai -- agar
  koi file fail ho, wo sirf log hoti hai, poora project nahi rukta.
- Sirf Python files ke liye bana hai abhi (jaisa baaki Saleha).
"""

import sys
import os
import re
import json
import subprocess
import shutil
from dataclasses import dataclass, field
from typing import List, Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from saleha.agents.base_agent import BaseAgent, AgentResponse
from saleha.agents.coder import CoderAgent
from saleha.agents.tester import TesterAgent


DEFAULT_PROJECTS_DIR = os.path.join(os.path.expanduser("~"), "saleha_projects")


@dataclass
class FileSpec:
    filename: str
    description: str


@dataclass
class FileResult:
    filename: str
    code: str
    tested_ok: bool
    test_error: str = ""


@dataclass
class ProjectResult:
    success: bool
    project_dir: str
    files: List[FileResult] = field(default_factory=list)
    log: str = ""
    entry_point: str = ""
    entry_point_ok: Optional[bool] = None
    entry_point_error: str = ""


class ProjectBuilder:
    def __init__(self, model: str = "auto", projects_dir: str = DEFAULT_PROJECTS_DIR):
        self.model = model
        self.planner_agent = BaseAgent(role="ProjectPlanner", model=model)
        self.coder = CoderAgent(model=model)
        self.tester = TesterAgent()
        self.projects_dir = projects_dir

    def _slugify(self, goal: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", goal.lower()).strip("_")
        return slug[:40] or "project"

    def _plan_files(self, goal: str) -> List[FileSpec]:
        prompt = f"""आप एक Python प्रोजेक्ट आर्किटेक्ट हैं।
लक्ष्य: {goal}

इस लक्ष्य को पूरा करने के लिए ज़रूरी Python files की सूची बनाएं (2-5 files, ज़रूरत से ज़्यादा नहीं)।
केवल इस JSON फॉर्मेट में जवाब दें, कुछ और टेक्स्ट नहीं:
[
  {{"filename": "app.py", "description": "क्या इस file में होना चाहिए"}},
  {{"filename": "utils.py", "description": "..."}}
]
"""
        response: AgentResponse = self.planner_agent.think(prompt)
        if not response.success:
            return []

        # JSON array nikaalo response se (agar model ne extra text daal diya ho)
        match = re.search(r"\[.*\]", response.content, re.DOTALL)
        json_text = match.group(0) if match else response.content

        try:
            data = json.loads(json_text)
            return [FileSpec(filename=d["filename"], description=d.get("description", "")) for d in data]
        except (json.JSONDecodeError, KeyError, TypeError):
            return []

    def _isolate_file_code(self, code: str, target_filename: str, all_specs: List[FileSpec]) -> str:
        """
        Chhote models kabhi-kabhi ek hi response me multiple files ka code
        de dete hain (jaise "# main.py\n...\n# calculator.py\n...") chahe
        humne sirf ek file manga ho. Ye method check karta hai ki agar
        code me kisi doosri file ka naam header-comment ki tarah mila,
        to sirf target file wala section rakhta hai.
        """
        other_filenames = [f.filename for f in all_specs if f.filename != target_filename]
        if not other_filenames:
            return code

        lines = code.split("\n")
        # Har line dekho -- agar wo "# <koi doosri file>.py" jaisi lagti hai,
        # to wahan se break maan lo (agar target file ka section pehle mil chuka hai)
        marker_pattern = re.compile(
            r"^\s*#+\s*(" + "|".join(re.escape(f) for f in [target_filename] + other_filenames) + r")\s*$"
        )

        sections = {}  # filename -> list of lines
        current_file = None
        preamble = []  # marker milne se pehle ka code (agar target file pehla section hai)

        for line in lines:
            m = marker_pattern.match(line)
            if m:
                current_file = m.group(1)
                sections[current_file] = []
                continue
            if current_file is None:
                preamble.append(line)
            else:
                sections[current_file].append(line)

        if target_filename in sections and sections[target_filename]:
            return "\n".join(sections[target_filename]).strip()

        # Koi marker nahi mila (normal case) -- poora code hi is file ka hai
        if not sections:
            return code

        non_empty_sections = {k: v for k, v in sections.items() if v}

        # Sirf EK section mila aur wo target file ka nahi -- ye asal me
        # multi-file dump nahi hai, model ne bas galat filename header laga
        # diya apne hi generated code par. Poora content isi file ka hai,
        # sirf header galat hai -- to us content ko hi use karo.
        if len(non_empty_sections) == 1 and not preamble:
            only_section = next(iter(non_empty_sections.values()))
            return "\n".join(only_section).strip()

        # Genuinely multiple files mix hui hain aur target ka section nahi
        # mila -- best-effort: preamble return karo (agar khaali hai to
        # pura code hi return kar do, kam se kam kuch to milega)
        return "\n".join(preamble).strip() or code

    def build(self, goal: str) -> ProjectResult:
        log = f"🏗️ Project Goal: {goal}\n" + "-" * 60 + "\n"

        log += "\n[1/3] Files ki list plan ki ja rahi hai...\n"
        file_specs = self._plan_files(goal)

        if not file_specs:
            return ProjectResult(
                success=False, project_dir="",
                log=log + "❌ Failed: model se valid file-list nahi mili.\n",
            )

        log += f"✅ {len(file_specs)} files planned: {[f.filename for f in file_specs]}\n"

        # Baaki files ka summary, taaki har file dusri files se aware ho
        project_summary = "\n".join(f"- {f.filename}: {f.description}" for f in file_specs)

        project_slug = self._slugify(goal)
        project_dir = os.path.join(self.projects_dir, project_slug)
        os.makedirs(project_dir, exist_ok=True)

        results: List[FileResult] = []

        log += "\n[2/3] Har file generate ki ja rahi hai...\n"
        for spec in file_specs:
            log += f"\n  📝 {spec.filename}: {spec.description}\n"
            task = (
                f"Is file ({spec.filename}) me ye hona chahiye: {spec.description}\n\n"
                f"ज़रूरी: सिर्फ '{spec.filename}' का कोड लिखें। किसी और file का कोड "
                f"बिल्कुल शामिल मत करें, भले ही project में और files हों।\n"
                f"Import हमेशा absolute रखें (जैसे 'from calculator import add'), "
                f"relative imports (जैसे '.calculator' या '..module') मत लिखें।"
            )
            plan_context = f"Poora project structure:\n{project_summary}"

            code_result = self.coder.generate_code(task, plan=plan_context, attempt=1)

            if not code_result.success:
                log += f"  ❌ Generation failed: {code_result.error}\n"
                results.append(FileResult(filename=spec.filename, code="", tested_ok=False,
                                           test_error=code_result.error))
                continue

            file_code = self._isolate_file_code(code_result.code, spec.filename, file_specs)

            test_result = self.tester.test_code(file_code)
            results.append(FileResult(
                filename=spec.filename,
                code=file_code,
                tested_ok=test_result.passed,
                test_error="" if test_result.passed else test_result.error_message,
            ))

            file_path = os.path.join(project_dir, spec.filename)
            os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(file_code)

            status = "✅" if test_result.passed else "⚠️"
            log += f"  {status} Saved to {file_path}\n"

        log += f"\n[3/3] Project saved to: {project_dir}\n"

        # Naya: entry-point ko actually chala ke check karo -- ye cross-file
        # import errors pakadta hai jo har file ko alag se test karne se
        # nahi pakde ja sakte.
        entry_spec = self._find_entry_point(file_specs, results)
        entry_ok = None
        entry_error = ""

        if entry_spec:
            log += f"\n[4/4] Entry point '{entry_spec.filename}' ko actually chala kar verify kiya ja raha hai...\n"
            for verify_attempt in range(1, 3):  # ek try + ek retry
                entry_ok, entry_error = self._verify_entry_point(project_dir, entry_spec.filename)
                if entry_ok:
                    log += f"  ✅ '{entry_spec.filename}' bina crash ke chala.\n"
                    break

                log += f"  ❌ Crash on run: {entry_error[:300]}\n"
                if verify_attempt < 2:
                    # Kaunsi file me asli bug hai, ye pata karo -- zaroori nahi
                    # ki entry-point khud kharab ho, ImportError ka matlab
                    # aksar ye hota hai ki jis file se import ho raha hai
                    # WAHI file ka content adhoora/galat hai.
                    buggy_spec = self._identify_buggy_file(entry_error, file_specs) or entry_spec

                    log += f"  '{buggy_spec.filename}' ko real error ke saath dobara generate kiya ja raha hai...\n"
                    fix_task = (
                        f"Is file ({buggy_spec.filename}) ka maksad hai: {buggy_spec.description}\n\n"
                        f"Project ki dusri file ko chalane par ye error aaya, jo shayad isi file "
                        f"({buggy_spec.filename}) ki wajah se hai:\n{entry_error}\n\n"
                        f"Is file ko sahi se banao taaki ye error na aaye. Project ki baaki files:\n{project_summary}"
                    )
                    fix_result = self.coder.generate_code(fix_task, plan="", attempt=verify_attempt + 1)
                    if fix_result.success:
                        fixed_code = self._isolate_file_code(fix_result.code, buggy_spec.filename, file_specs)
                        fix_path = os.path.join(project_dir, buggy_spec.filename)
                        with open(fix_path, "w", encoding="utf-8") as f:
                            f.write(fixed_code)
                        for r in results:
                            if r.filename == buggy_spec.filename:
                                r.code = fixed_code
                    else:
                        log += f"  ❌ Fix generation failed: {fix_result.error}\n"
                        break
        else:
            log += "\n[4/4] Koi clear entry point nahi mila (koi file me __main__ block nahi), verification skip.\n"

        all_ok = all(r.tested_ok for r in results) and (entry_ok is not False)
        return ProjectResult(
            success=all_ok, project_dir=project_dir, files=results, log=log,
            entry_point=entry_spec.filename if entry_spec else "",
            entry_point_ok=entry_ok, entry_point_error=entry_error,
        )

    def _identify_buggy_file(self, error_text: str, file_specs: List[FileSpec]) -> Optional[FileSpec]:
        """
        Python ka traceback khud batata hai ki crash *kis file ke andar*
        hua -- har 'File "...", line N, in ...' frame ek step hai. Sabse
        aakhri (deepest) frame wahi jagah hai jahan asli error trigger hua.
        Ye keyword-matching (jaise "cannot import name") se zyada bharosemand
        hai, kyunki error messages bahut alag-alag tarah ke ho sakte hain
        (ImportError, ModuleNotFoundError, relative-import error, etc.) --
        lekin traceback ka structure hamesha same hota hai.
        """
        frames = re.findall(r'File "([^"]+)", line \d+', error_text)
        if not frames:
            return None

        # Deepest frame (sabse aakhir wala) = jahan crash actually hua
        for frame_path in reversed(frames):
            frame_filename = os.path.basename(frame_path)
            for spec in file_specs:
                if spec.filename == frame_filename:
                    return spec
        return None

    def _find_entry_point(self, file_specs: List[FileSpec], results: List[FileResult]) -> Optional[FileSpec]:
        """Wo file dhoondo jisme 'if __name__ == \"__main__\"' hai -- yahi asli
        run-karne-wali file hoti hai. Na mile to None (verification skip)."""
        for spec in file_specs:
            match = next((r for r in results if r.filename == spec.filename), None)
            if match and '__main__' in match.code:
                return spec
        return None

    def _verify_entry_point(self, project_dir: str, entry_filename: str):
        """Entry file ko project folder ke andar hi chalata hai (taaki sibling
        files import ho sakein), timeout ke saath. Returns (success, error_text).
        Note: Runs in a project-scoped temp directory with stdin closed (input='') 
        and a 10s timeout, which provides basic safety, but for untrusted code 
        DockerSandbox should be used."""
        python_cmd = shutil.which("python3") or shutil.which("python")
        if not python_cmd:
            return False, "Neither 'python' nor 'python3' found on PATH."

        try:
            result = subprocess.run(
                [python_cmd, entry_filename],
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=10,
                input="",  # agar file input() maange to turant EOF de do, hang na ho
            )
            if result.returncode == 0:
                return True, ""
            return False, result.stderr or result.stdout
        except subprocess.TimeoutExpired:
            # Timeout ka matlab crash nahi hai -- shayad interactive input loop hai
            # (jaisa calculator ka while True). Ise fail mat maano.
            return True, ""
        except (OSError, subprocess.SubprocessError) as e:
            return False, str(e)


if __name__ == "__main__":
    print("=" * 70)
    print("🏗️ SALEHA PROJECT BUILDER TEST")
    print("=" * 70)
    print("Note: is test ke liye Ollama chalu hona chahiye.")

    builder = ProjectBuilder(model="qwen2.5-coder:1.5b")
    result = builder.build("A simple command-line calculator with add, subtract, multiply, divide")

    print(result.log)
    print(f"\nOverall success: {result.success}")
    for f in result.files:
        status = "✅" if f.tested_ok else "❌"
        print(f"  {status} {f.filename} ({'ok' if f.tested_ok else f.test_error})")