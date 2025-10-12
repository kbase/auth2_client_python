"""
Convert the async client to a sync client.
"""

from pathlib import Path
import unasync


def main():
    additional_replacements = {
        "AsyncKBaseAuthClient": "KBaseAuthClient",
        "AsyncClient": "Client",
        "aclose": "close",
    }
    
    
    rules = [
        unasync.Rule(
            fromdir="/src/kbase/_auth/_async/",
            todir="/src/kbase/_auth/_sync/",
            additional_replacements=additional_replacements,
        ),
    ]
    
    filepaths = [
        str(Path(__file__).parent.parent / "src" / "kbase" / "_auth" / "_async" / "client.py")
    ]
    
    unasync.unasync_files(filepaths, rules)


if __name__ == "__main__":
    main()
