"""Utility: parse `llm_data_ClearenceJobs.json` and sort roles by company and score.

Outputs:
 - JSON file with companies and sorted role lists
 - Optional CSV with flattened rows

Usage:
    python sort_llm_results.py --input llm_data_ClearenceJobs.json --output-json sorted.json --top-n 5
"""

from __future__ import annotations
import _init__
import argparse
import csv
import json
import os
import re
from typing import Any, Dict, List, Optional
import glob
from datetime import datetime
import pandas as pd


def parse_score(s: Any) -> Optional[float]:
    """Parse a score value into a float (0-100). Returns None if missing/invalid."""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    if isinstance(s, str):
        s = s.strip()
        if s == "":
            return None
        m = re.search(r"[-+]?\d+(?:\.\d+)?", s)
        if not m:
            return None
        try:
            return float(m.group(0))
        except Exception:
            return None
    return None


def load_master_json(path: str) -> Dict[str, Dict[str, Dict[str, Any]]]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_master_from_folder(folder: str, pattern: str = 'llm_data_ClearenceJobs_*.json', *, dedup_policy: str = 'higher_score', conflict_report_path: Optional[str] = None) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Load and merge multiple master JSON files from a folder matching pattern.

    Supports a deduplication policy when the same (company, role) key appears in multiple files.
    - dedup_policy='latest' -> later files overwrite earlier entries (original behavior)
    - dedup_policy='higher_score' -> replace existing entry only if the incoming score is higher

    Also tracks a link map to ensure a single canonical mapping from job link -> (company, role).
    When a link collision is found (same link for different roles), the first-seen mapping is kept and
    the later occurrence is annotated with a link conflict (the 'link' field is removed from the later
    entry and a 'link_conflict' + 'link_conflict_with' are added).

    Optionally writes a conflict report (JSON) to `conflict_report_path` when duplicates/conflicts are observed,
    and writes a `link_map.json` file next to it containing the canonical link-to-role mapping.
    """
    files = sorted(glob.glob(os.path.join(folder, pattern)))
    if not files:
        raise FileNotFoundError(f'No files found in {folder} matching {pattern}')
    master: Dict[str, Dict[str, Dict[str, Any]]] = {}
    conflicts: List[Dict[str, Any]] = []
    link_map: Dict[str, Dict[str, Any]] = {}

    for fp in files:
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                m = json.load(f)
        except Exception as e:
            print(f'Warning: failed to load {fp}: {e}')
            continue

        file_mtime = os.path.getmtime(fp)
        file_ts = datetime.fromtimestamp(file_mtime).isoformat()
        for company, roles in m.items():
            if company not in master:
                master[company] = {}
            for role, detail in roles.items():
                existing = master[company].get(role)

                occurrence = {
                    'file': os.path.basename(fp),
                    'timestamp': file_ts,
                    'score': detail.get('score')
                }

                # Normalize link value for link_map tracking
                link_val = detail.get('link')
                link_key = None
                if isinstance(link_val, str) and link_val.strip() != '':
                    link_key = link_val.strip()

                # Helper to record a link collision: mark incoming detail with conflict info and
                # do not overwrite the canonical link_map mapping.
                def _record_link_collision(new_detail, existing_assoc):
                    new_detail['link_conflict'] = True
                    new_detail['link_conflict_with'] = existing_assoc
                    # remove link to avoid duplicate mapping
                    if 'link' in new_detail:
                        del new_detail['link']

                if existing is None:
                    new_detail = dict(detail)
                    # new_detail.setdefault('provenance', [])
                    # new_detail['provenance'].append(occurrence)
                    new_detail['chosen_by'] = 'initial'

                    # Link map bookkeeping
                    if link_key:
                        if link_key in link_map:
                            # link already associated with a different role
                            assoc = link_map[link_key]
                            if assoc['company'] != company or assoc['role'] != role:
                                _record_link_collision(new_detail, assoc)
                                conflicts.append({
                                    'type': 'link_collision',
                                    'link': link_key,
                                    'existing_company': assoc['company'],
                                    'existing_role': assoc['role'],
                                    'existing_file': assoc['file'],
                                    'new_company': company,
                                    'new_role': role,
                                    'new_file': os.path.basename(fp),
                                    'decision': 'keep_existing'
                                })
                        else:
                            link_map[link_key] = {'company': company, 'role': role, 'file': os.path.basename(fp), 'timestamp': file_ts}

                    master[company][role] = new_detail
                else:
                    existing_score = parse_score(existing.get('score'))
                    new_score = parse_score(detail.get('score'))
                    existing_score_val = existing_score if existing_score is not None else -1
                    new_score_val = new_score if new_score is not None else -1

                    decision = None
                    replaced = False
                    if dedup_policy == 'latest':
                        ## overwrite and carry prior provenance
                        new_detail = dict(detail)
                        # prev_prov = existing.get('provenance', [])
                        # new_detail.setdefault('provenance', [])
                        # new_detail['provenance'] = prev_prov + [occurrence]
                        new_detail['chosen_by'] = 'latest'
                        replaced = True
                        decision = 'replaced'
                    elif dedup_policy == 'higher_score':
                        # replace only if incoming score is higher
                        if new_score_val > existing_score_val:
                            new_detail = dict(detail)
                            # prev_prov = existing.get('provenance', [])
                            # new_detail.setdefault('provenance', [])
                            # new_detail['provenance'] = prev_prov + [occurrence]
                            new_detail['chosen_by'] = 'higher_score'
                            replaced = True
                            decision = 'replaced'
                        else:
                            ## keep existing; record provenance of duplicate occurrence
                            # existing.setdefault('provenance', [])
                            # existing['provenance'].append(occurrence)
                            existing.setdefault('chosen_by', 'kept_by_higher_score')
                            decision = 'kept'
                    else:
                        # fallback to latest semantics
                        new_detail = dict(detail)
                        # prev_prov = existing.get('provenance', [])
                        # new_detail.setdefault('provenance', [])
                        # new_detail['provenance'] = prev_prov + [occurrence]
                        new_detail['chosen_by'] = 'latest'
                        replaced = True
                        decision = 'replaced'

                    # If we are replacing, handle link map collisions for the incoming detail
                    if replaced:
                        if link_key:
                            if link_key in link_map:
                                assoc = link_map[link_key]
                                if assoc['company'] != company or assoc['role'] != role:
                                    # collision: keep the existing mapping and strip link from incoming
                                    _record_link_collision(new_detail, assoc)
                                    conflicts.append({
                                        'type': 'link_collision',
                                        'link': link_key,
                                        'existing_company': assoc['company'],
                                        'existing_role': assoc['role'],
                                        'existing_file': assoc['file'],
                                        'new_company': company,
                                        'new_role': role,
                                        'new_file': os.path.basename(fp),
                                        'decision': 'keep_existing'
                                    })
                            else:
                                # no collision: associate link to this (company,role)
                                link_map[link_key] = {'company': company, 'role': role, 'file': os.path.basename(fp), 'timestamp': file_ts}

                        master[company][role] = new_detail

                    # record conflict info for diagnostics (score-based conflicts)
                    if decision in ('replaced', 'kept'):
                        conflicts.append({
                            'type': 'score_conflict',
                            'company': company,
                            'role': role,
                            'existing_score': existing_score_val,
                            'new_score': new_score_val,
                            # 'existing_file': existing.get('provenance', [{}])[0].get('file'),
                            'new_file': os.path.basename(fp),
                            'decision': decision,
                            'chosen_by': 'higher_score' if dedup_policy == 'higher_score' else 'latest'
                        })

    # Write conflicts report if requested
    if conflict_report_path and conflicts:
        try:
            with open(conflict_report_path, 'w', encoding='utf-8') as cf:
                json.dump({'conflicts': conflicts}, cf, indent=2, ensure_ascii=False)
            print(f'Wrote conflict report to {conflict_report_path} ({len(conflicts)} conflicts)')
        except Exception as e:
            print(f'Warning: failed to write conflict report {conflict_report_path}: {e}')

    # Optionally write the canonical link map next to the conflict report
    if conflict_report_path and link_map:
        try:
            link_map_path = os.path.join(os.path.dirname(conflict_report_path), 'link_map.json')
            with open(link_map_path, 'w', encoding='utf-8') as lf:
                json.dump({'link_map': link_map}, lf, indent=2, ensure_ascii=False)
            print(f'Wrote link map to {link_map_path} ({len(link_map)} links)')
        except Exception as e:
            print(f'Warning: failed to write link map: {e}')

    return master


def combine_llmout(folder: str = 'JobData\\ClearanceJobs\\llmIn\\', pattern: str = 'llm_data_ClearenceJobs_*.json', *, descending: bool = True, dedup_policy: str = 'higher_score', return_link_map: bool = False):
    """Load and merge all matching JSON files in `folder` and return a flattened + sorted mapping.

    This is a convenience wrapper around :func:`load_master_from_folder` + :func:`flatten_and_sort`.

    Args:
        folder: Directory containing batch JSON files (default: 'llmOut').
        pattern: Glob pattern to match files in the folder.
        descending: Sort order for scores (default: True -> highest first).
        dedup_policy: How to resolve duplicate (company, role) keys; default 'higher_score'.
        return_link_map: If True, return a dict with keys 'by_company' and 'link_map'. Default False for backward compatibility.

    Returns:
        If return_link_map is False (default) returns a dict mapping company -> list of role dicts (with normalized numeric 'score').
        If return_link_map is True returns {'by_company': {...}, 'link_map': {...}}.
    """
    conflict_path = os.path.join(folder, 'merge_conflicts.json')
    master = load_master_from_folder(folder, pattern=pattern, dedup_policy=dedup_policy, conflict_report_path=conflict_path)
    sorted_by_company = flatten_and_sort(master, descending=descending)

    if return_link_map:
        link_map_path = os.path.join(os.path.dirname(conflict_path), 'link_map.json')
        link_map = {}
        if os.path.exists(link_map_path):
            try:
                with open(link_map_path, 'r', encoding='utf-8') as lf:
                    lm = json.load(lf)
                    link_map = lm.get('link_map', {})
            except Exception:
                link_map = {}
        return {'by_company': sorted_by_company, 'link_map': link_map}

    return sorted_by_company


def flatten_and_sort(master: Dict[str, Dict[str, Dict[str, Any]]], *, descending: bool = True) -> Dict[str, List[Dict[str, Any]]]:
    """Return mapping company -> sorted list of role dicts with normalized score."""
    out: Dict[str, List[Dict[str, Any]]] = {}
    for company, roles in master.items():
        role_list: List[Dict[str, Any]] = []
        for role_name, detail in roles.items():
            score = parse_score(detail.get('score'))
            if score < 80:
                continue
            row = {
                'company': company,
                'role_name': role_name,
                'score': score if score is not None else -1,
                # 'raw_score': detail.get('score'),
                'fit_reason': detail.get('fit_reason'),
                'missing_skills': detail.get('missing_skills'),
                'link': detail.get('link'),
                **{k: v for k, v in detail.items() if k not in ('score', 'fit_reason', 'missing_skills', 'link')}
            }
            role_list.append(row)

        # Sort: treat missing scores (score == -1) as lowest
        role_list.sort(key=lambda r: (r['score'] if r['score'] is not None else -1), reverse=descending)
        out[company] = role_list
    return out


def write_json(path: str, data: Dict[str, List[Dict[str, Any]]], pretty: bool = True) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        if pretty:
            json.dump(data, f, indent=2, ensure_ascii=False)
        else:
            json.dump(data, f, separators=(',', ':'), ensure_ascii=False)


def write_csv(path: str, data: Dict[str, List[Dict[str, Any]]]) -> None:
    # Flatten rows
    rows = []
    for company, roles in data.items():
        for r in roles:
            rows.append({
                'company': company,
                'role_name': r.get('role_name'),
                'score': r.get('score'),
                'fit_reason': r.get('fit_reason'),
                'missing_skills': json.dumps(r.get('missing_skills') or []),
                'link': r.get('link')
            })

    if not rows:
        print('No rows to write to CSV.')
        return

    fieldnames = ['company', 'role_name', 'score', 'fit_reason', 'missing_skills', 'link']
    with open(path, 'w', encoding='utf-8', newline='') as csvf:
        writer = csv.DictWriter(csvf, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def data_to_dataframe(data: Dict[str, List[Dict[str, Any]]]) -> 'pd.DataFrame':
    """Convert the sorted data into a Pandas DataFrame for easier human reading.

    The returned DataFrame is sorted by company and score (desc).
    """
    rows = []
    for company, roles in data.items():
        for r in roles:
            row = {
                'company': company,
                'role_name': r.get('role_name'),
                'score': r.get('score'),
                'fit_reason': r.get('fit_reason'),
                'missing_skills': r.get('missing_skills') or [],
                'link': r.get('link')
            }
            # include any other fields present
            extras = {k: v for k, v in r.items() if k not in row and k not in ('missing_skills',)}
            row.update(extras)
            rows.append(row)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    # Ensure score is numeric
    df['score'] = pd.to_numeric(df['score'], errors='coerce').fillna(-1)
    df.sort_values(by=['company', 'score'], ascending=[True, False], inplace=True)
    return df


def summarize(data: Dict[str, List[Dict[str, Any]]], top_n: Optional[int] = None, min_score: Optional[float] = None) -> None:
    total_companies = len(data)
    total_roles = sum(len(v) for v in data.values())
    print(f'Companies: {total_companies}, Roles: {total_roles}')

    for company, roles in data.items():
        filtered = roles
        if min_score is not None:
            filtered = [r for r in filtered if (r.get('score', -1) >= min_score)]
        if top_n is not None:
            filtered = filtered[:top_n]
        
        for r in filtered:
            sc = r.get('score')
            sc_text = 'N/A' if sc == -1 else f'{sc:.1f}'
            if float(sc_text) > 80:
                print(f'\n{company} ({len(filtered)} roles shown)')
                print(f"  - {r['role_name']} | score: {sc_text} | link: {r.get('link')}")
            
def cli(argv=None):
    p = argparse.ArgumentParser(description='Sort LLM job matches by company and score')
    p.add_argument('--input', '-i', default='llm_data_ClearenceJobs.json', help='Input master JSON file')
    p.add_argument('--output-json', '-oj', default='sorted_by_company.json', help='Output JSON summary file')
    p.add_argument('--output-csv', '-oc', default=None, help='Optional output CSV file')
    p.add_argument('--top-n', type=int, default=5, help='Top N roles per company to show in console')
    p.add_argument('--min-score', type=float, default=None, help='Filter out roles below this score when showing summary')
    p.add_argument('--desc', action='store_true', help='Sort descending (highest first). Default: True')
    p.add_argument('--no-pretty', action='store_true', help='Write compact JSON instead of pretty')
    p.add_argument('--input-folder', default='JobData/ClearanceJobs/llmIn', help='Directory containing batch JSONs to merge (default: llmOut)')
    p.add_argument('--glob-pattern', default='llm_data_ClearenceJobs_*.json', help='Glob pattern to match files inside --input-folder')
    p.add_argument('--merge', action='store_true', help='Merge all matching files into a single combined summary (instead of per-file outputs)')
    p.add_argument('--dedup-policy', choices=['latest', 'higher_score'], default='higher_score', help='Deduplication policy when the same (company, role) appears in multiple files')
    p.add_argument('--to-pandas', action='store_true', help='Produce a Pandas DataFrame and print a readable summary')
    p.add_argument('--output-pandas-csv', default=None, help='Save the DataFrame to CSV')
    p.add_argument('--output-html', default=None, help='Save the DataFrame to HTML')
    args = p.parse_args(argv)

    # Load master either from a single input file or by scanning a folder of batch outputs
    if args.input_folder:
        if not os.path.isdir(args.input_folder):
            raise SystemExit(f'Input folder not found: {args.input_folder}')
        files = sorted(glob.glob(os.path.join(args.input_folder, args.glob_pattern)))
        if not files:
            raise SystemExit(f'No files found in {args.input_folder} matching {args.glob_pattern}')
        print(f'Found {len(files)} files in {args.input_folder} matching {args.glob_pattern}')

        # Always build a combined single JSON summary for the folder (so the summary contains all entries)
        try:
            # First scan files to compute counts and duplicate occurrences
            total_role_instances = 0
            role_occurrences = {}  # (company, role) -> count
            file_errors = []
            for fp in files:
                try:
                    with open(fp, 'r', encoding='utf-8') as f:
                        m = json.load(f)
                except Exception as e:
                    file_errors.append((fp, str(e)))
                    continue
                for company, roles in m.items():
                    for role in roles.keys():
                        total_role_instances += 1
                        key = (company.strip(), role.strip())
                        role_occurrences[key] = role_occurrences.get(key, 0) + 1

            unique_roles = len(role_occurrences)
            duplicate_keys = {k: v for k, v in role_occurrences.items() if v > 1}

            print(f'Files scanned: {len(files)} (errors: {len(file_errors)})')
            print(f'Total role entries found across files: {total_role_instances}')
            print(f'Unique role keys (company+role): {unique_roles}; duplicates: {len(duplicate_keys)}')
            if duplicate_keys:
                print('Top duplicate role keys (count >1):')
                # show up to 10 duplicates sorted by frequency desc
                for (company, role), cnt in sorted(duplicate_keys.items(), key=lambda x: x[1], reverse=True)[:10]:
                    print(f'  - ({cnt}x) {company} | {role}')

            # Now load and merge files according to dedup policy
            conflict_path = os.path.join(args.input_folder, 'merge_conflicts.json')
            combined_master = load_master_from_folder(args.input_folder, pattern=args.glob_pattern, dedup_policy=args.dedup_policy, conflict_report_path=conflict_path)
            combined_sorted = flatten_and_sort(combined_master, descending=not args.desc)

            # Determine combined output path for JSON
            if args.output_json:
                combined_out_json = args.output_json
                if not os.path.isabs(combined_out_json) and os.path.dirname(combined_out_json) == '':
                    combined_out_json = os.path.join(args.input_folder, combined_out_json)
            else:
                combined_out_json = os.path.join(args.input_folder, 'sorted_by_company.json')

            # If the link_map was created by the loader, include it alongside the combined results
            link_map_path = os.path.join(args.input_folder, 'link_map.json')
            link_map = None
            if os.path.exists(link_map_path):
                try:
                    with open(link_map_path, 'r', encoding='utf-8') as lf:
                        lm = json.load(lf)
                        link_map = lm.get('link_map')
                except Exception:
                    link_map = None

            if link_map is not None:
                combined_package = {'by_company': combined_sorted, 'link_map': link_map}
                write_json(combined_out_json, combined_package, pretty=not args.no_pretty)
                print(f'Wrote combined JSON summary (with link_map) to {combined_out_json}')
                print(f'Links: {len(link_map)}')
            else:
                write_json(combined_out_json, combined_sorted, pretty=not args.no_pretty)
                print(f'Wrote combined JSON summary to {combined_out_json}')

            # Print combined summary to console
            summarize(combined_sorted, top_n=args.top_n, min_score=args.min_score)
            if link_map is not None:
                # Count collisions from conflict file if present for reporting
                conflicts = []
                conflict_path = os.path.join(args.input_folder, 'merge_conflicts.json')
                if os.path.exists(conflict_path):
                    try:
                        with open(conflict_path, 'r', encoding='utf-8') as cf:
                            cr = json.load(cf)
                            conflicts = cr.get('conflicts', [])
                    except Exception:
                        conflicts = []
                link_collisions = sum(1 for c in conflicts if c.get('type') == 'link_collision')
                print(f'Link collisions detected: {link_collisions}')

        except Exception as e:
            print(f'Warning: failed to build combined summary: {e}')
            # If user explicitly asked to merge, write combined CSV/DF/HTML and return
            if args.merge:
                if args.output_csv:
                    out_csv = args.output_csv
                    if not os.path.isabs(out_csv) and os.path.dirname(out_csv) == '':
                        out_csv = os.path.join(args.input_folder, out_csv)
                    write_csv(out_csv, combined_sorted)
                    print(f'Wrote combined CSV summary to {out_csv}')

                if args.to_pandas or args.output_pandas_csv or args.output_html:
                    df = data_to_dataframe(combined_sorted)
                    if df.empty:
                        print('No rows available to build a DataFrame for combined output.')
                    else:
                        if args.to_pandas:
                            if args.top_n and args.top_n > 0:
                                top_df = df.groupby('company', group_keys=False).apply(lambda g: g.nlargest(args.top_n, 'score'))
                                print(top_df.reset_index(drop=True).to_string(index=False))
                            else:
                                print(df.to_string(index=False))
                        if args.output_pandas_csv:
                            out_pandas_csv = args.output_pandas_csv
                            if not os.path.isabs(out_pandas_csv) and os.path.dirname(out_pandas_csv) == '':
                                out_pandas_csv = os.path.join(args.input_folder, out_pandas_csv)
                            df.to_csv(out_pandas_csv, index=False)
                            print(f'Wrote combined DataFrame CSV to {out_pandas_csv}')
                        if args.output_html:
                            out_html = args.output_html
                            if not os.path.isabs(out_html) and os.path.dirname(out_html) == '':
                                out_html = os.path.join(args.input_folder, out_html)
                            df.to_html(out_html, index=False)
                            print(f'Wrote combined DataFrame HTML to {out_html}')
                return

#             # Optional combined CSV (single file)
#             if args.output_csv:
#                 out_csv = args.output_csv
#                 if not os.path.isabs(out_csv) and os.path.dirname(out_csv) == '':
#                     out_csv = os.path.join(args.input_folder, out_csv)
#                 write_csv(out_csv, sorted_by_company)
#                 print(f'Wrote combined CSV summary to {out_csv}')

#             summarize(sorted_by_company, top_n=args.top_n, min_score=args.min_score)

#             if args.to_pandas or args.output_pandas_csv or args.output_html:
#                 df = data_to_dataframe(sorted_by_company)
#                 if df.empty:
#                     print('No rows available to build a DataFrame for combined output.')
#                 else:
#                     if args.to_pandas:
#                         if args.top_n and args.top_n > 0:
#                             top_df = df.groupby('company', group_keys=False).apply(lambda g: g.nlargest(args.top_n, 'score'))
#                             print(top_df.reset_index(drop=True).to_string(index=False))
#                         else:
#                             print(df.to_string(index=False))
#                     if args.output_pandas_csv:
#                         out_pandas_csv = args.output_pandas_csv
#                         if not os.path.isabs(out_pandas_csv) and os.path.dirname(out_pandas_csv) == '':
#                             out_pandas_csv = os.path.join(args.input_folder, out_pandas_csv)
#                         df.to_csv(out_pandas_csv, index=False)
#                         print(f'Wrote combined DataFrame CSV to {out_pandas_csv}')
#                     if args.output_html:
#                         out_html = args.output_html
#                         if not os.path.isabs(out_html) and os.path.dirname(out_html) == '':
#                             out_html = os.path.join(args.input_folder, out_html)
#                         df.to_html(out_html, index=False)
#                         print(f'Wrote combined DataFrame HTML to {out_html}')
#             return

        # Otherwise process each file individually (existing behavior)
        for idx, fp in enumerate(files, start=1):
            print(f'Processing ({idx}/{len(files)}): {fp}')
            try:
                master = load_master_json(fp)
            except Exception as e:
                print(f'Warning: failed to load {fp}: {e}')
                continue

            sorted_by_company = flatten_and_sort(master, descending=not args.desc)
            base = os.path.splitext(os.path.basename(fp))[0].split('_ClearenceJobs_')[-1]
            print(f'File base identifier: {base}')
            # JSON output (suffix with source basename)
            if args.output_json:
                # base_outname = os.path.splitext(os.path.basename(args.output_json))[0]
                base_outname = f'sorted_by_company_'
                out_dirname = 'JobData/ClearanceJobs/llmOut/'
                out_path = os.path.join(out_dirname, f'{base_outname}_{base}.json')
            else:
                out_path = f'sorted_by_company_{base}.json'
            write_json(out_path, sorted_by_company, pretty=not args.no_pretty)
            print(f'Wrote JSON summary to {out_path}')

            # optional CSV output
            if args.output_csv:
                base_csvname = os.path.splitext(os.path.basename(args.output_csv))[0]
                csv_dir = os.path.dirname(args.output_csv) or '.'
                csv_out = os.path.join(csv_dir, f'{base_csvname}_{base}.csv')
                write_csv(csv_out, sorted_by_company)
                print(f'Wrote CSV summary to {csv_out}')

            # Console summary
            summarize(sorted_by_company, top_n=args.top_n, min_score=args.min_score)

            # pandas outputs per file
            if args.to_pandas or args.output_pandas_csv or args.output_html:
                df = data_to_dataframe(sorted_by_company)
                if df.empty:
                    print('No rows available to build a DataFrame for this file.')
                else:
                    if args.to_pandas:
                        if args.top_n and args.top_n > 0:
                            top_df = df.groupby('company', group_keys=False).apply(lambda g: g.nlargest(args.top_n, 'score'))
                            print(top_df.reset_index(drop=True).to_string(index=False))
                        else:
                            print(df.to_string(index=False))
                    if args.output_pandas_csv:
                        pandas_csv_out = os.path.splitext(args.output_pandas_csv)[0] + f'_{base}.csv'
                        pandas_csv_out = os.path.join(os.path.dirname(args.output_pandas_csv) or '.', os.path.basename(pandas_csv_out))
                        df.to_csv(pandas_csv_out, index=False)
                        print(f'Wrote DataFrame CSV to {pandas_csv_out}')
                    if args.output_html:
                        html_out = os.path.splitext(args.output_html)[0] + f'_{base}.html'
                        html_out = os.path.join(os.path.dirname(args.output_html) or '.', os.path.basename(html_out))
                        df.to_html(html_out, index=False)
                        print(f'Wrote DataFrame HTML to {html_out}')
        # Done processing folder
        return

    # Single input file path
    if not os.path.exists(args.input):
        raise SystemExit(f'Input file not found: {args.input}')
    master = load_master_json(args.input)

    sorted_by_company = flatten_and_sort(master, descending=not args.desc)

    write_json(args.output_json, sorted_by_company, pretty=not args.no_pretty)
    print(f'Wrote JSON summary to {args.output_json}')

    if args.output_csv:
        write_csv(args.output_csv, sorted_by_company)
        print(f'Wrote CSV summary to {args.output_csv}')

    summarize(sorted_by_company, top_n=args.top_n, min_score=args.min_score)

    # Optionally convert to a Pandas DataFrame for easier human reading and saving
    if args.to_pandas or args.output_pandas_csv or args.output_html:
        df = data_to_dataframe(sorted_by_company)
        if df.empty:
            print('No rows available to build a DataFrame.')
        else:
            if args.to_pandas:
                # Show the top N per company for readable console output
                if args.top_n and args.top_n > 0:
                    top_df = df.groupby('company', group_keys=False).apply(lambda g: g.nlargest(args.top_n, 'score'))
                    print(top_df.reset_index(drop=True).to_string(index=False))
                else:
                    print(df.to_string(index=False))
            if args.output_pandas_csv:
                df.to_csv(args.output_pandas_csv, index=False)
                print(f'Wrote DataFrame CSV to {args.output_pandas_csv}')
            if args.output_html:
                df.to_html(args.output_html, index=False)
                print(f'Wrote DataFrame HTML to {args.output_html}')


def create_master_json_from_folder(folder_path: str, output_filename: str) -> Dict[str, Any]:
    """
    Iterates through all JSON files in a folder and merges them into one dictionary.
    """
    master_data = {}
    
    # 1. Validate folder exists
    while not os.path.isdir(folder_path):
        print(f"Folder not found: {folder_path}")
        folder_path = input("Please enter a valid path to the JSON folder: ")

    # 2. Iterate through files
    files = [f for f in os.listdir(folder_path) if f.endswith('.json')]
    print(f"Found {len(files)} files to consolidate in {folder_path}")

    for filename in files:
        file_path = os.path.join(folder_path, filename)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # Assuming data is a dictionary or a list of dictionaries
                # If your data is keyed by Job ID or Link, update logic here:
                if isinstance(data, dict):
                    master_data.update(data)
                elif isinstance(data, list):
                    # If it's a list, we might need a key to prevent duplicates
                    for item in data:
                        job_id = item.get('job_link') or item.get('id')
                        if job_id:
                            master_data[job_id] = item
        except Exception as e:
            print(f"Error skipping file {filename}: {e}")

    # 3. Save the combined master file
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(master_data, f, indent=4)
        
    print(f"✅ Success! Combined {len(files)} files into {output_filename}")
    return master_data

import pandas as pd
import json

def generate_job_report(master_json_path):
    # 1. Load the grouped JSON
    with open(master_json_path, 'r', encoding='utf-8') as f:
        grouped_data = json.load(f)

    # 2. Flatten the Dictionary of Lists into a Single List
    flattened_jobs = []
    
    # Iterate through each company key (e.g., "Leidos", "SAIC")
    for company_name, jobs in grouped_data.items():
        if isinstance(jobs, list):
            for job in jobs:
                if job and isinstance(job, dict):
                    # Ensure the company name is inside the job dict
                    # (In your sample it already is, but this is a safe guard)
                    job['company'] = job.get('company', company_name)
                    flattened_jobs.append(job)

    # 3. Create the DataFrame from the flat list
    df = pd.DataFrame(flattened_jobs)

    if df.empty:
        print("⚠️ No valid job data found in the master file.")
        return pd.DataFrame()

    # 4. Clean Numeric Data
    # Fill missing scores with 0 and convert to integer
    if 'score' in df.columns:
        df['score'] = pd.to_numeric(df['score'], errors='coerce').fillna(0).astype(int)
    else:
        df['score'] = 0

    # 5. Sort by Score (Desc) and Company (Asc)
    df_sorted = df.sort_values(by=['score', 'company'], ascending=[False, True])

    # 6. Select Clean View
    # We drop 'full_description' for the terminal view because it's massive
    display_cols = ['score', 'company', 'role_name', 'location','link']
    final_cols = [c for c in display_cols if c in df_sorted.columns]
    
    return df_sorted[final_cols]

########################################    
### Main                             ###
########################################

# report_df = generate_job_report('MasterJobData.json')
# print(report_df.to_string(index=False))# Usage
# out_dir = 'JobData/ClearanceJobs/llmOut'
# master = create_master_json_from_folder(out_dir, "JobData/ClearanceJobs/MASTER_ANALYSIS.json")
if __name__ == '__main__':
    
    cli()
    folder_path = 'JobData/ClearanceJobs/llmOut'
    output_filename = "JobData/ClearanceJobs/MASTER_ANALYSIS.json"
    create_master_json_from_folder(folder_path, output_filename)
    print(generate_job_report(output_filename))