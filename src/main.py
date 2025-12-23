"""CLI entrypoint for running jobs."""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        description="Student Ops Discord Notifier",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.main canvas --dry-run
  python -m src.main daily-brief
  python -m src.main news --dry-run
  python -m src.main weekly
        """
    )
    
    parser.add_argument(
        "job",
        choices=["canvas", "daily-brief", "news", "weekly"],
        help="Job to run"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print messages instead of posting to Discord"
    )
    
    args = parser.parse_args()
    
    # Import and run the appropriate job
    if args.job == "canvas":
        from src.jobs.run_canvas import run
        run(dry_run=args.dry_run)
    
    elif args.job == "daily-brief":
        from src.jobs.run_daily_brief import run
        run(dry_run=args.dry_run)
    
    elif args.job == "news":
        from src.jobs.run_news import run
        run(dry_run=args.dry_run)
    
    elif args.job == "weekly":
        from src.jobs.run_weekly_report import run
        run(dry_run=args.dry_run)
    
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
