"""Every registered command must resolve the names its callback references.

`saleha jarvis` raised `NameError: name 'voice_cmd' is not defined` on every
invocation. The forward target moved to `voice_vision.py` when the monolithic
`commands.py` was split, and this call site was left pointing at a name that
no longer existed in its module -- a shipped command that could not run at
all.

The suite could not see it: the command registers fine, so importing the CLI
and counting commands stays green. Only calling it fails. This checks the
whole registry, so the next split cannot reintroduce the same class of break
silently.
"""

import unittest

from click.testing import CliRunner

from saleha.cli.commands import cli


class JarvisCommandTests(unittest.TestCase):

    def test_jarvis_does_not_raise_nameerror(self) -> None:
        """With no arguments it should reach its own argument validation,
        not die resolving a missing module-level name."""
        result = CliRunner().invoke(cli, ["jarvis"])
        self.assertNotIsInstance(result.exception, NameError)

    def test_jarvis_reports_its_own_usage_error(self) -> None:
        result = CliRunner().invoke(cli, ["jarvis"])
        combined = (result.output or "") + str(result.exception or "")
        self.assertIn("must be provided", combined)


class EveryCommandCallbackResolvesItsGlobalsTests(unittest.TestCase):
    """A cheap static sweep for the same defect anywhere else in the CLI."""

    @staticmethod
    def _unresolved_globals(func) -> list:
        """Names the callback loads globally that its module does not define.

        Uses co_names against the function's own module namespace and
        builtins. This is deliberately conservative: it only reports a name
        when the module genuinely cannot supply it.
        """
        import builtins

        code = getattr(func, "__code__", None)
        if code is None:
            return []
        module_globals = getattr(func, "__globals__", {})
        missing = []
        for name in code.co_names:
            if name in module_globals or hasattr(builtins, name):
                continue
            # Attribute names share co_names with globals, so only flag a
            # name that is loaded as a global by this code object.
            missing.append(name)
        return missing

    def test_no_command_callback_references_a_name_its_module_lacks(self) -> None:
        import dis

        offenders = []
        for name, command in cli.commands.items():
            callback = getattr(command, "callback", None)
            if callback is None or not hasattr(callback, "__code__"):
                continue
            module_globals = getattr(callback, "__globals__", {})
            import builtins
            for instruction in dis.get_instructions(callback.__code__):
                if instruction.opname != "LOAD_GLOBAL":
                    continue
                target = instruction.argval
                if target in module_globals or hasattr(builtins, target):
                    continue
                offenders.append(f"{name} -> {target}")
        self.assertEqual(offenders, [], f"unresolvable global loads: {offenders}")


if __name__ == "__main__":
    unittest.main()
