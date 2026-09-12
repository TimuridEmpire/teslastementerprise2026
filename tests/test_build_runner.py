from __future__ import annotations

from enterprise_router.build_runner import BuildRunnerManager


def test_extract_files_ignores_rag_quoted_source_from_a_prior_artifact():
    """Regression test: reproduced live building a clock app. Once artifacts
    embed their own generated source (engineering_agent.py's _artifact_body),
    RAG retrieval can quote a PRIOR artifact's full body -- including that
    prior artifact's own "## Generated Source" section -- as background
    context inside the CURRENT artifact's "## Engineering Request" section.
    That produced two "## Generated Source" headings in one artifact, and a
    naive whole-document regex scan matched a code fence spanning from the
    first (quoted, truncated) heading all the way to the real closing fence
    of the current build's own file, misattributing clock_app.py's real
    source under the quoted weather_app.py filename entirely. Extraction
    must anchor to the artifact's own section (always the last occurrence)."""
    content = (
        "## Engineering Request\n\n"
        "Feature: Clock App\n\n"
        "--- The section below is background only, from unrelated prior "
        "work. Do NOT implement anything described in it -- implement "
        "ONLY the spec above. ---\n\n"
        "## Related prior engineering specs/code (semantic retrieval)\n"
        "- [Engineering] Engineering Feature Implementation (similarity 0.69): "
        "# Engineering Feature Implementation\n\n## Generated Source\n\n"
        "### `weather_app.py`\n\n```python\nclass WeatherApp:\n"
        "    def get_forecast(self, city, temperature_celsius):\n"
        "        if not isinstance(temperature_celsius, (int, float)):\n"
        "            raise ValueError(\"Temperature must be a number\")\n"
        "        if temperature_celsius < 10:\n\n"
        "## Generated Files\n\n- `clock_app.py`\n\n"
        "## Test Status\n\npassed\n\n"
        "## Generated Source\n\n"
        "### `clock_app.py`\n\n"
        "```python\n"
        "class Clock:\n"
        "    def current_time(self, hour, minute, second):\n"
        "        return f'{hour:02}:{minute:02}:{second:02}'\n"
        "```\n"
    )

    files = BuildRunnerManager().extract_files(content)

    assert set(files.keys()) == {"clock_app.py"}
    assert "class Clock" in files["clock_app.py"]
    assert "WeatherApp" not in files["clock_app.py"]
