from pathlib import Path


def test_webapp_root_and_staging_pages_point_to_legal_domain():
    root_html = Path("webapp/index.html").read_text(encoding="utf-8")
    staging_html = Path("webapp/t/index.html").read_text(encoding="utf-8")

    for html in (root_html, staging_html):
        assert "https://dream-wheels-ai-legal.vercel.app/legal/offer" in html
        assert "https://dream-wheels-ai-legal.vercel.app/legal/privacy" in html
        assert 'href="#"' not in html
