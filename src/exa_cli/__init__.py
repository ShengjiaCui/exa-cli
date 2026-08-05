"""exa-cli — a thin command-line interface for the Exa.ai search API.

Symmetric in spirit to the `tvly` CLI for Tavily: reads EXA_API_KEY from the
environment, exposes search / contents / find-similar / answer subcommands, and
emits JSON via --json for agent consumption. Zero third-party dependencies
(stdlib urllib only) so the install stays isolated.
"""

__version__ = "0.1.0"
