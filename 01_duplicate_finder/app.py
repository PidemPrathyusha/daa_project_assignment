
"""Find duplicate contents and copy files into an organized folder."""

import sys
import filecmp
import hashlib
import shutil
from pathlib import Path

# Allow importing common.py from the parent folder
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import Store, form, heading, note, table, run


# Store preview plan and information about created copies
store = Store(
    Path(__file__).with_name("data.json"),
    {"plan": []}
)


def scan(folder):
    """
    Scan the selected folder and its subfolders.

    Returns:
        root: selected folder
        files: all regular files found
        duplicates: confirmed duplicate file groups
    """

    root = Path(folder).expanduser().resolve()

    # Check that the supplied path is a directory
    if not root.is_dir():
        raise ValueError("Enter an existing folder path.")

    groups = {}
    files = []

    # Walk through the folder and all subfolders
    for path in sorted(root.rglob("*")):

        # Skip symbolic links and non-files
        if path.is_symlink() or not path.is_file():
            continue

        # Skip the application's own organized output
        if "_organized" in path.relative_to(root).parts:
            continue

        # Create SHA-256 fingerprint
        digest = hashlib.sha256()

        # Read the file in 65,536-byte chunks
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(65536), b""):
                digest.update(chunk)

        # Group using file size + SHA-256 fingerprint
        key = (
            path.stat().st_size,
            digest.hexdigest()
        )

        groups.setdefault(key, []).append(path)
        files.append(path)

    # Confirm duplicate contents using filecmp
    duplicates = []

    for (size, _), paths in groups.items():

        if len(paths) > 1:

            equal = [
                p
                for p in paths
                if filecmp.cmp(paths[0], p, shallow=False)
            ]

            if len(equal) > 1:
                duplicates.append((size, equal))

    return root, files, duplicates


def build_plan(root, files):
    """
    Build a list of source and destination pairs.

    No files are copied here.
    This function only creates the preview plan.
    """

    plan = []

    for index, source in enumerate(files, 1):

        # Example:
        # report.pdf -> pdf
        # photo.jpg  -> jpg
        # README     -> no_extension
        category = (
            source.suffix.lower().lstrip(".")
            or "no_extension"
        )

        # Add sequence number to avoid filename collisions
        target = (
            root
            / "_organized"
            / category
            / f"{index}_{source.name}"
        )

        plan.append([
            str(source),
            str(target)
        ])

    return plan


def view():
    """
    Display the browser interface.

    This function only displays information.
    It does not scan, copy, or delete files.
    """

    out = note(
        "Enter a folder containing practice files. "
        "Originals are retained."
    )

    out += form(
        "scan",
        [
            ("folder", "Full folder path", "text", "")
        ],
        "Scan and preview"
    )

    out += heading("Last organization preview")

    out += table(
        ["Original", "Proposed copy"],
        store.data["plan"]
    )

    out += form(
        "copy",
        [],
        "Create organized copies"
    )

    out += form(
        "undo",
        [],
        "Undo last copy operation"
    )

    return out


def handle(data):
    """
    Handle scan, copy, and undo actions.
    """

    # ---------------------------------------------------------
    # 1. SCAN
    # ---------------------------------------------------------
    if data["action"] == "scan":

        # Do not create another plan while copies are active
        if store.data.get("created"):
            raise ValueError(
                "Undo the previous copy before preparing another plan."
            )

        # Scan folder
        root, files, duplicates = scan(data["folder"])

        # Create preview plan
        store.data["plan"] = build_plan(root, files)

        # Save the plan
        store.save()

        # Prepare duplicate table
        rows = [
            (p.name, str(p), size)
            for size, paths in duplicates
            for p in paths
        ]

        # Calculate redundant storage
        waste = sum(
            size * (len(paths) - 1)
            for size, paths in duplicates
        )

        return (
            heading("Duplicate groups")
            + note(
                f"Redundant copies occupy {waste} bytes."
            )
            + table(
                ["Name", "Path", "Bytes"],
                rows
            )
        )

    # ---------------------------------------------------------
    # 2. COPY
    # ---------------------------------------------------------
    if data["action"] == "copy":

        # A plan must exist and there must not already be
        # an active copy operation
        if (
            not store.data["plan"]
            or store.data.get("created")
        ):
            raise ValueError(
                "Prepare a new preview first, or undo the last copy."
            )

        # Safety checks before copying
        for source, target in store.data["plan"]:

            if not Path(source).is_file():
                raise ValueError(
                    "A source is missing. Scan again."
                )

            if Path(target).exists():
                raise ValueError(
                    "A destination already exists. Scan again."
                )

        # Keep track of created copies
        store.data["created"] = []
        store.save()

        # Create every planned copy
        for source, target in store.data["plan"]:

            target_path = Path(target)

            # Create destination folder
            target_path.parent.mkdir(
                parents=True,
                exist_ok=True
            )

            # Copy file and preserve metadata
            shutil.copy2(source, target)

            # Calculate fingerprint of the copied file
            fingerprint = hashlib.sha256(
                target_path.read_bytes()
            ).hexdigest()

            # Record copied path and fingerprint
            store.data["created"].append({
                "path": target,
                "hash": fingerprint
            })

            # Save immediately
            store.save()

        return note(
            "Organized copies created. "
            "Original files have not been changed."
        )

    # ---------------------------------------------------------
    # 3. UNDO
    # ---------------------------------------------------------
    if data["action"] == "undo":

        # First verify that none of the copied files
        # has been modified
        for entry in store.data.get("created", []):

            target = Path(entry["path"])

            if target.exists():

                current_hash = hashlib.sha256(
                    target.read_bytes()
                ).hexdigest()

                if current_hash != entry["hash"]:
                    raise ValueError(
                        "A copied file was edited. "
                        "Move it elsewhere before undoing."
                    )

        # Remove the tracked copies
        for entry in store.data.get("created", []):

            Path(entry["path"]).unlink(
                missing_ok=True
            )

        # Clear undo information and preview
        store.data["created"] = []
        store.data["plan"] = []

        store.save()

        return note(
            "Copies removed. "
            "Empty category folders may remain."
        )

    # ---------------------------------------------------------
    # Unknown action
    # ---------------------------------------------------------
    raise ValueError("Unknown action.")


# Start the application when app.py is run directly
if __name__ == "__main__":
    run(
        "Duplicate File Finder and Organizer",
        view,
        handle
    )

