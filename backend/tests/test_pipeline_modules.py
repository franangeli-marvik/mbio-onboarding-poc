"""
Module-level tests for the interview prep pipeline.
Each module is tested in isolation with timing measurements.
Usage: cd backend && python -m tests.test_pipeline_modules
"""
import json
import sys
import time
from pathlib import Path

RESUME_PATH = Path(__file__).resolve().parents[2] / "Francesco_Angeli_resume (6).pdf"
PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
WARN = "\033[93mWARN\033[0m"
THRESHOLD_SECONDS = 15


def _header(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def _report(label: str, elapsed: float, success: bool, detail: str = "") -> None:
    status = PASS if success else FAIL
    flag = f" {WARN} SLOW" if elapsed > THRESHOLD_SECONDS else ""
    print(f"  [{status}] {label}: {elapsed:.2f}s{flag}")
    if detail:
        print(f"         {detail}")


def test_resume_parser() -> dict | None:
    _header("1. Resume Parser (Gemini 3 Flash)")

    if not RESUME_PATH.exists():
        print(f"  [{FAIL}] Resume not found: {RESUME_PATH}")
        return None

    from resume.parser import parse_resume

    file_bytes = RESUME_PATH.read_bytes()
    start = time.time()
    try:
        result = parse_resume(
            file_bytes=file_bytes,
            mime_type="application/pdf",
            filename=RESUME_PATH.name,
        )
        elapsed = time.time() - start

        name = result.get("basics", {}).get("name", "?")
        work_count = len(result.get("work", []))
        skills_count = len(result.get("skills", []))
        gaps_count = len(result.get("_mbio", {}).get("gaps_to_explore", []))

        _report(
            "parse_resume",
            elapsed,
            bool(name and work_count),
            f"name={name}, work={work_count}, skills={skills_count}, gaps={gaps_count}",
        )
        return result

    except Exception as e:
        elapsed = time.time() - start
        _report("parse_resume", elapsed, False, str(e))
        return None


def test_profile_analyzer(resume_data: dict) -> dict | None:
    _header("2. Profile Analyzer (Gemini 2.0 Flash)")

    from interview_prep.agents.profile_analyzer import profile_analyzer_node
    from interview_prep.schemas import InterviewPrepState

    state: InterviewPrepState = {
        "resume_data": resume_data,
        "life_stage": "professional",
        "user_name": resume_data.get("basics", {}).get("name", "Candidate"),
        "tenant_config": {
            "tenant_id": "acme_corp",
            "company_name": "Acme Corporation",
            "tone": "direct",
            "focus_area": "ML systems design, model deployment, MLOps",
            "custom_instructions": "Focus on quantifiable achievements. Probe for system design decisions and trade-offs. Ask about scale (data volume, QPS, team size).",
            "position_id": "senior_ml_engineer",
            "position_title": "Senior ML Engineer",
        },
        "profile_analysis": None,
        "interview_plan": None,
        "interview_briefing": None,
        "errors": [],
    }

    start = time.time()
    try:
        result = profile_analyzer_node(state)
        elapsed = time.time() - start

        pa = result.get("profile_analysis")
        errors = result.get("errors", [])

        if pa:
            _report(
                "profile_analyzer",
                elapsed,
                True,
                f"domain={pa.get('domain')}, strengths={len(pa.get('strengths', []))}, "
                f"gaps={len(pa.get('gaps', []))}, hooks={len(pa.get('interesting_hooks', []))}",
            )
            return pa
        else:
            _report("profile_analyzer", elapsed, False, f"errors={errors}")
            return None

    except Exception as e:
        elapsed = time.time() - start
        _report("profile_analyzer", elapsed, False, str(e))
        return None


def test_question_planner(resume_data: dict, profile_analysis: dict) -> dict | None:
    _header("3. Question Planner (Gemini 2.0 Flash)")

    from interview_prep.agents.question_planner import question_planner_node
    from interview_prep.schemas import InterviewPrepState

    user_name = resume_data.get("basics", {}).get("name", "Candidate")

    state: InterviewPrepState = {
        "resume_data": resume_data,
        "life_stage": "professional",
        "user_name": user_name,
        "tenant_config": {
            "tenant_id": "acme_corp",
            "company_name": "Acme Corporation",
            "tone": "direct",
            "focus_area": "ML systems design, model deployment, MLOps",
            "custom_instructions": "Focus on quantifiable achievements. Probe for system design decisions and trade-offs. Ask about scale (data volume, QPS, team size).",
            "position_id": "senior_ml_engineer",
            "position_title": "Senior ML Engineer",
        },
        "profile_analysis": profile_analysis,
        "interview_plan": None,
        "interview_briefing": None,
        "errors": [],
    }

    start = time.time()
    try:
        result = question_planner_node(state)
        elapsed = time.time() - start

        ip = result.get("interview_plan")
        errors = result.get("errors", [])

        if ip:
            phases = ip.get("phases", [])
            total_q = sum(len(p.get("questions", [])) for p in phases)
            _report(
                "question_planner",
                elapsed,
                True,
                f"phases={len(phases)}, questions={total_q}, "
                f"duration={ip.get('total_estimated_duration')}",
            )
            return ip
        else:
            _report("question_planner", elapsed, False, f"errors={errors}")
            return None

    except Exception as e:
        elapsed = time.time() - start
        _report("question_planner", elapsed, False, str(e))
        return None


def test_interview_briefer(
    resume_data: dict, profile_analysis: dict, interview_plan: dict
) -> dict | None:
    _header("4. Interview Briefer (Gemini 2.0 Flash)")

    from interview_prep.agents.interview_briefer import interview_briefer_node
    from interview_prep.schemas import InterviewPrepState

    user_name = resume_data.get("basics", {}).get("name", "Candidate")

    state: InterviewPrepState = {
        "resume_data": resume_data,
        "life_stage": "professional",
        "user_name": user_name,
        "tenant_config": {
            "tenant_id": "acme_corp",
            "company_name": "Acme Corporation",
            "tone": "direct",
            "focus_area": "ML systems design, model deployment, MLOps",
            "custom_instructions": "Focus on quantifiable achievements. Probe for system design decisions and trade-offs. Ask about scale (data volume, QPS, team size).",
            "position_id": "senior_ml_engineer",
            "position_title": "Senior ML Engineer",
        },
        "profile_analysis": profile_analysis,
        "interview_plan": interview_plan,
        "interview_briefing": None,
        "errors": [],
    }

    start = time.time()
    try:
        result = interview_briefer_node(state)
        elapsed = time.time() - start

        ib = result.get("interview_briefing")
        errors = result.get("errors", [])

        if ib:
            _report(
                "interview_briefer",
                elapsed,
                True,
                f"questions={len(ib.get('questions_script', []))}, "
                f"hints={len(ib.get('personalization_hints', []))}",
            )
            return ib
        else:
            _report("interview_briefer", elapsed, False, f"errors={errors}")
            return None

    except Exception as e:
        elapsed = time.time() - start
        _report("interview_briefer", elapsed, False, str(e))
        return None


def main() -> None:
    print("\n" + "=" * 60)
    print("  PIPELINE MODULE TESTS")
    print(f"  Resume: {RESUME_PATH.name}")
    print("=" * 60)

    total_start = time.time()
    timings: dict[str, float] = {}

    t0 = time.time()
    resume_data = test_resume_parser()
    timings["resume_parser"] = time.time() - t0

    if not resume_data:
        print(f"\n  [{FAIL}] Cannot continue without parsed resume.")
        sys.exit(1)

    t0 = time.time()
    profile_analysis = test_profile_analyzer(resume_data)
    timings["profile_analyzer"] = time.time() - t0

    if not profile_analysis:
        print(f"\n  [{FAIL}] Cannot continue without profile analysis.")
        sys.exit(1)

    t0 = time.time()
    interview_plan = test_question_planner(resume_data, profile_analysis)
    timings["question_planner"] = time.time() - t0

    if not interview_plan:
        print(f"\n  [{FAIL}] Cannot continue without interview plan.")
        sys.exit(1)

    t0 = time.time()
    interview_briefing = test_interview_briefer(
        resume_data, profile_analysis, interview_plan
    )
    timings["interview_briefer"] = time.time() - t0

    total_elapsed = time.time() - total_start

    _header("SUMMARY")
    for module, elapsed in timings.items():
        flag = f" *** SLOW ***" if elapsed > THRESHOLD_SECONDS else ""
        print(f"  {module:25s} {elapsed:7.2f}s{flag}")
    print(f"  {'TOTAL':25s} {total_elapsed:7.2f}s")
    print()

    all_ok = all([resume_data, profile_analysis, interview_plan, interview_briefing])
    if all_ok:
        print(f"  [{PASS}] All modules passed.")
    else:
        print(f"  [{FAIL}] Some modules failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
