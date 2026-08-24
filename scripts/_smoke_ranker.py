import os
import tempfile

from saleha.core.repo_context_packer import RepoContextPacker

tmp = tempfile.mkdtemp()
src = os.path.join(tmp, "src")
os.makedirs(src)
with open(os.path.join(src, "types.js"), "w") as f:
    f.write("export class Money {\n  constructor(cents){ this.cents = cents; }\n}\n")
for i in range(6):
    with open(os.path.join(src, f"use{i}.js"), "w") as f:
        f.write('import { Money } from "./types.js";\nconst t' + str(i) + ' = new Money(' + str(i) + ');\n')

p = RepoContextPacker(root_dir=tmp)
ctx = p.pack("money handling utilities")
print(ctx[:600])
print("...")
print("types.js in context:", "types.js" in ctx)
