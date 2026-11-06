"""Try the checker from a terminal:  python -m app.cli "https://bit.ly/xyz"  [--sw] [--json]"""
import asyncio
import json
import sys

from .pipeline import check_message
from .scoring import detect_lang, format_reply


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        sys.exit(1)
    text = " ".join(args)
    results = asyncio.run(check_message(text))
    if "--json" in sys.argv:
        print(json.dumps([r.to_dict() for r in results], indent=2, ensure_ascii=False))
        return
    lang = "sw" if "--sw" in sys.argv else detect_lang(text)
    print(format_reply(results, lang))
    for r in results:
        print(f"\n[debug] score={r.score} chain={' -> '.join(r.chain)} "
              f"signals={[s.code for s in r.signals]}")


if __name__ == "__main__":
    main()
