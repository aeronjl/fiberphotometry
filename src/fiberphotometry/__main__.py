"""Allow ``python -m fiberphotometry`` to invoke the CLI."""

from fiberphotometry.cli import main

raise SystemExit(main())
