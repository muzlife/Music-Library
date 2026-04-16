from pathlib import Path


ROOT = Path("/Volumes/Works/07.hahahoho")
SMOKE_SCRIPT = ROOT / "scripts" / "run_smoke_qa.py"


def test_run_smoke_qa_defaults_to_qa_endpoints_and_label():
    text = SMOKE_SCRIPT.read_text("utf-8")

    assert "EXTERNAL_BASE_URL = 'https://qa-library.muzlife.com'" in text
    assert "LOCAL_BASE_URL = 'http://127.0.0.1:8100'" in text
    assert "com.muzlife.library-qa" in text
    assert "os.getuid()" in text
