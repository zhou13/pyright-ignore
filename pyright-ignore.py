import argparse
import json
import sys
from difflib import unified_diff
from pathlib import Path


def add_type_ignore_comments(json_data, inplace=False, show_diff=False):
    modified_files = {}
    ignored_lines = {}
    remove_ignore_lines = {}

    for diagnostic in json_data["generalDiagnostics"]:
        file_path = Path(diagnostic["file"])
        if not file_path.exists():
            print(f"Warning: File {file_path} not found. Skipping.", file=sys.stderr)
            continue

        if file_path not in modified_files:
            with file_path.open("r") as file:
                modified_files[file_path] = file.readlines()
            ignored_lines[file_path] = set()
            remove_ignore_lines[file_path] = set()

        lines = modified_files[file_path]
        line_number = diagnostic["range"]["start"]["line"]

        if diagnostic["rule"] == "reportUnnecessaryTypeIgnoreComment":
            if 0 <= line_number < len(lines):
                remove_ignore_lines[file_path].add(line_number)
        elif (
            0 <= line_number < len(lines)
            and line_number not in ignored_lines[file_path]
        ):
            if not lines[line_number].strip().endswith("# type: ignore"):
                lines[line_number] = lines[line_number].rstrip() + "  # type: ignore\n"
                ignored_lines[file_path].add(line_number)
        elif line_number >= len(lines):
            print(
                f"Warning: Line {line_number + 1} in {file_path} is out of range. Skipping.",
                file=sys.stderr,
            )

    # Process removals after all additions to avoid conflicts
    for file_path, lines in modified_files.items():
        for line_number in remove_ignore_lines[file_path]:
            if lines[line_number].strip().endswith("# type: ignore"):
                lines[line_number] = (
                    lines[line_number].split("# type: ignore")[0].rstrip() + "\n"
                )
            elif lines[line_number].strip().endswith("# pyright: ignore"):
                lines[line_number] = (
                    lines[line_number].split("# pyright: ignore")[0].rstrip() + "\n"
                )
            else:
                print(
                    f"Error: Ignore comment not found at line {line_number}.",
                    file=sys.stderr,
                )

    if inplace:
        for file_path, lines in modified_files.items():
            with file_path.open("w") as file:
                file.writelines(lines)
        print("Type ignore comments processed successfully.", file=sys.stderr)
    elif show_diff:
        for file_path, modified_lines in modified_files.items():
            with file_path.open("r") as file:
                original_lines = file.readlines()
            diff = unified_diff(
                original_lines,
                modified_lines,
                fromfile=str(file_path),
                tofile=str(file_path),
            )
            sys.stdout.writelines(diff)
    else:
        for file_path, lines in modified_files.items():
            print(f"--- {file_path} ---")
            sys.stdout.writelines(lines)
            print()


def main():
    parser = argparse.ArgumentParser(
        description="Add '# type: ignore' comments to lines with Pyright errors."
    )
    parser.add_argument(
        "json_file",
        nargs="?",
        type=argparse.FileType("r"),
        default=sys.stdin,
        help="Path to the Pyright JSON output file (default: stdin)",
    )
    parser.add_argument(
        "-i",
        "--inplace",
        action="store_true",
        help="Modify files in-place",
    )
    parser.add_argument(
        "-d",
        "--diff",
        action="store_true",
        help="Show changes in unified diff format",
    )
    args = parser.parse_args()

    if args.inplace and args.diff:
        print(
            "Error: --inplace and --diff options are mutually exclusive.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        json_data = json.load(args.json_file)
        add_type_ignore_comments(json_data, args.inplace, args.diff)
    except json.JSONDecodeError:
        print("Error: Invalid JSON input", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {str(e)}", file=sys.stderr)
        sys.exit(1)
    finally:
        if args.json_file is not sys.stdin:
            args.json_file.close()


if __name__ == "__main__":
    main()
