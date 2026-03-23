from pathlib import Path
import importlib.util

target = Path(__file__).with_name("Prohpo asistent Final.py")
spec = importlib.util.spec_from_file_location("prohypo_final", target)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
app = module.app

if __name__ == "__main__":
    app.run(
        host=module.os.getenv("HOST", "0.0.0.0"),
        port=int(module.os.getenv("PORT", "5000")),
        debug=module.os.getenv("FLASK_DEBUG", "0") == "1",
    )
