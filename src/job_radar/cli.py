"""Command-line interface for Remote Job Radar.

Commands:
  job-radar profile --cv path/to/cv.pdf   Generate candidate_profile.json from a CV
  job-radar search [--dry-run]            Run the daily search and email the digest
"""

from __future__ import annotations

import argparse
import sys

from .common.config import Config
from .common.logger import get_logger, setup_logging
from .profile_engine import ProfileGenerator, extract_text
from .profile_engine.models import CandidateProfile
from .providers import get_provider
from .search_engine.pipeline import SearchPipeline

logger = get_logger(__name__)


def _cmd_profile(args: argparse.Namespace, config: Config) -> int:
    text = extract_text(args.cv)
    provider = get_provider(config)
    profile = ProfileGenerator(provider).generate(text)
    out = args.out or config.profile_file
    profile.save(out)
    print(f"✅ Profile written to {out}")
    print(f"   Seniority: {profile.seniority or '?'} | "
          f"{profile.years_experience} yrs | "
          f"{len(profile.skills)} skills")
    print(f"   Search terms: {', '.join(profile.search_terms[:8])}")
    return 0


def _cmd_search(args: argparse.Namespace, config: Config) -> int:
    if not config.profile_file.exists():
        print(
            f"❌ No profile found at {config.profile_file}. "
            f"Run 'job-radar profile --cv your_cv.pdf' first.",
            file=sys.stderr,
        )
        return 1
    profile = CandidateProfile.load(config.profile_file)
    pipeline = SearchPipeline(config)
    result = pipeline.run(profile, dry_run=args.dry_run)

    print(
        f"📊 Collected {result.collected} → {result.new} new → "
        f"{result.shortlisted} shortlisted → {result.emailed} emailed"
    )
    if args.dry_run and result.jobs:
        print("\nTop matches (dry run, not emailed):")
        for s in result.jobs:
            print(f"  [{s.final_score:>3}] {s.job.title} — {s.job.company} "
                  f"({s.job.remote_region})")
            print(f"        {s.job.url}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="job-radar", description="AI-powered remote job matching from a CV."
    )
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--env", default=".env", help="Path to .env")
    sub = parser.add_subparsers(dest="command", required=True)

    p_profile = sub.add_parser("profile", help="Generate the candidate profile from a CV PDF")
    p_profile.add_argument("--cv", required=True, help="Path to the CV PDF")
    p_profile.add_argument("--out", help="Output path (defaults to config.profile_file)")
    p_profile.set_defaults(func=_cmd_profile)

    p_search = sub.add_parser("search", help="Run the daily search and email the digest")
    p_search.add_argument(
        "--dry-run", action="store_true", help="Rank but do not send email or record history"
    )
    p_search.set_defaults(func=_cmd_search)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = Config.load(args.config, args.env)
    setup_logging(config.log_level)
    try:
        return args.func(args, config)
    except Exception as exc:
        logger.error("%s", exc)
        if config.log_level.upper() == "DEBUG":
            raise
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
