"""Allow ``python -m fipha`` to invoke the CLI."""

from fipha.cli import main

raise SystemExit(main())
