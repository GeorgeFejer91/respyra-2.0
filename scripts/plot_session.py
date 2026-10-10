#!/usr/bin/env python3
"""Plot a Respyra XDF (primary input) or a legacy session CSV.

Usage: python scripts/plot_session.py recording.xdf --no-show
The installed engine includes this command; summaries are also saved automatically.
"""

from mpi.session_summary import (
    compute_baseline_cal,
    compute_trial_stats,
    load_session,
    load_xdf_session,
    main,
    plot_session,
    save_xdf_summary,
)

if __name__ == "__main__":
    main()
