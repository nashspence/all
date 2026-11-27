"""Tiny warm-call wrapper. The parent owns the only acceptance clock."""
import contextlib
import importlib.util
import json
import os
import sys

sys.dont_write_bytecode = True


def main():
    adapter, subject, work = sys.argv[1:]
    control = sys.stdout

    def send(kind, repeat=None, **extra):
        control.write(json.dumps(dict(kind=kind, repeat=repeat, **extra)) + "\n")
        control.flush()

    # Ordinary adapter logging cannot be confused with completion frames.
    with contextlib.redirect_stdout(sys.stderr):
        sys.path.insert(0, subject)
        spec = importlib.util.spec_from_file_location("_approved_performance_adapter", adapter)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        context = module.prepare(subject, work)
        send("ready")
        value, last_repeat = None, None
        for line in sys.stdin:
            request = json.loads(line)
            kind, repeat = request["kind"], request.get("repeat")
            if kind == "run":
                value = module.run(context, repeat)
                last_repeat = repeat
                send("complete", repeat)
            elif kind == "verify" and repeat == last_repeat:
                verified = module.verify(context, value, repeat)
                if "ALL_PERFORMANCE_FEATURES" in os.environ:
                    send("verified", repeat, witness=verified)
                elif verified is not True:
                    raise RuntimeError("approved output verifier did not return True")
                else:
                    send("verified", repeat)
            elif kind == "close":
                if hasattr(module, "close"):
                    module.close(context)
                send("closed")
                return
            else:
                raise RuntimeError("invalid worker request")


if __name__ == "__main__":
    main()
