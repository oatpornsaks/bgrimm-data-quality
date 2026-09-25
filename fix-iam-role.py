#!/usr/bin/env python3
"""
Script to fix IamRole in Glue DQ job JSON files.

This script ensures that IamRole in AmazonRedshiftSource nodes has both
'Label' and 'Value' fields with the full ARN.

Usage:
    # Check all jobs (dry-run)
    python fix-iam-role.py --check

    # Fix a specific job
    python fix-iam-role.py glue-dq/bgrimm-datagov-solar-roof-dq-2-2025/bgrimm-datagov-solar-roof-dq-2-2025.json

    # Fix all jobs
    python fix-iam-role.py --all

    # Fix all jobs with custom IAM role ARN
    python fix-iam-role.py --all --iam-role arn:aws:iam::123456789012:role/my-role
"""

import json
import argparse
import os
import sys
from pathlib import Path

# Default IAM role ARN
DEFAULT_IAM_ROLE_ARN = "arn:aws:iam::140023373092:role/bgrimm-datagov-glue-dq-redshift-s3-unload-role"


def fix_iam_role_in_nodes(nodes_str: str, iam_role_arn: str) -> tuple[str, int]:
    """
    Fix IamRole in codeGenConfigurationNodes.
    
    Returns:
        tuple: (fixed_nodes_str, count_of_fixes)
    """
    nodes = json.loads(nodes_str)
    fix_count = 0
    
    for node_name, node in nodes.items():
        if 'AmazonRedshiftSource' in node:
            data = node['AmazonRedshiftSource']['Data']
            iam_role = data.get('IamRole', {})
            
            # Check if fix is needed
            needs_fix = False
            
            if not iam_role:
                # No IamRole at all
                needs_fix = True
            elif 'Value' not in iam_role:
                # Missing Value field
                needs_fix = True
            elif 'arn:aws:iam' not in iam_role.get('Value', ''):
                # Value doesn't contain full ARN
                needs_fix = True
            
            if needs_fix:
                # Fix the IamRole
                data['IamRole'] = {
                    'Label': iam_role_arn,
                    'Value': iam_role_arn
                }
                fix_count += 1
    
    return json.dumps(nodes), fix_count


def check_job_file(file_path: str) -> dict:
    """
    Check IamRole status in a job file.
    
    Returns:
        dict with status info
    """
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    nodes_str = data.get('codeGenConfigurationNodes', '{}')
    nodes = json.loads(nodes_str)
    
    results = {
        'file': file_path,
        'job_name': data.get('name', 'unknown'),
        'sources': [],
        'needs_fix': False
    }
    
    for node_name, node in nodes.items():
        if 'AmazonRedshiftSource' in node:
            source_name = node['AmazonRedshiftSource'].get('Name', node_name)
            iam_role = node['AmazonRedshiftSource']['Data'].get('IamRole', {})
            
            has_label = 'Label' in iam_role
            has_value = 'Value' in iam_role
            has_arn_in_value = 'arn:aws:iam' in iam_role.get('Value', '')
            
            status = '✅' if (has_label and has_value and has_arn_in_value) else '❌'
            
            if status == '❌':
                results['needs_fix'] = True
            
            results['sources'].append({
                'name': source_name,
                'status': status,
                'label': iam_role.get('Label', 'N/A'),
                'value': iam_role.get('Value', 'N/A'),
                'has_value': has_value,
                'has_arn': has_arn_in_value
            })
    
    return results


def fix_job_file(file_path: str, iam_role_arn: str, dry_run: bool = False) -> dict:
    """
    Fix IamRole in a job file.
    
    Returns:
        dict with fix results
    """
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    nodes_str = data.get('codeGenConfigurationNodes', '{}')
    fixed_nodes_str, fix_count = fix_iam_role_in_nodes(nodes_str, iam_role_arn)
    
    result = {
        'file': file_path,
        'job_name': data.get('name', 'unknown'),
        'fixes_applied': fix_count,
        'dry_run': dry_run
    }
    
    if fix_count > 0 and not dry_run:
        data['codeGenConfigurationNodes'] = fixed_nodes_str
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    return result


def find_all_job_files(base_dir: str) -> list:
    """Find all Glue job JSON files in glue-dq directory."""
    glue_dq_dir = Path(base_dir) / 'glue-dq'
    job_files = []
    
    for job_dir in glue_dq_dir.iterdir():
        if job_dir.is_dir() and job_dir.name.startswith('bgrimm-datagov-'):
            json_file = job_dir / f"{job_dir.name}.json"
            if json_file.exists():
                job_files.append(str(json_file))
    
    return sorted(job_files)


def main():
    parser = argparse.ArgumentParser(
        description='Fix IamRole in Glue DQ job JSON files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        'files',
        nargs='*',
        help='Job JSON files to fix'
    )
    
    parser.add_argument(
        '--check',
        action='store_true',
        help='Check IamRole status without making changes'
    )
    
    parser.add_argument(
        '--all',
        action='store_true',
        help='Process all job files in glue-dq directory'
    )
    
    parser.add_argument(
        '--iam-role',
        default=DEFAULT_IAM_ROLE_ARN,
        help=f'IAM role ARN to use (default: {DEFAULT_IAM_ROLE_ARN})'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be changed without modifying files'
    )
    
    args = parser.parse_args()
    
    # Get base directory
    base_dir = Path(__file__).parent
    
    # Determine which files to process
    if args.all:
        files = find_all_job_files(base_dir)
    elif args.files:
        files = [str(Path(base_dir) / f) if not os.path.isabs(f) else f for f in args.files]
    else:
        # Default: check all
        args.check = True
        files = find_all_job_files(base_dir)
    
    if not files:
        print("No job files found.")
        sys.exit(1)
    
    print(f"IAM Role ARN: {args.iam_role}")
    print(f"Processing {len(files)} file(s)...\n")
    
    if args.check:
        # Check mode
        needs_fix_count = 0
        
        for file_path in files:
            result = check_job_file(file_path)
            
            status_icon = '❌' if result['needs_fix'] else '✅'
            print(f"{status_icon} {result['job_name']}")
            
            for source in result['sources']:
                print(f"   {source['status']} {source['name']}")
                if source['status'] == '❌':
                    print(f"      Label: {source['label']}")
                    print(f"      Value: {source['value']}")
            
            if result['needs_fix']:
                needs_fix_count += 1
            
            print()
        
        print(f"\nSummary: {len(files) - needs_fix_count}/{len(files)} jobs OK")
        if needs_fix_count > 0:
            print(f"         {needs_fix_count} jobs need fixing")
            print(f"\nTo fix all jobs, run:")
            print(f"  python fix-iam-role.py --all")
    
    else:
        # Fix mode
        total_fixes = 0
        fixed_files = 0
        
        for file_path in files:
            result = fix_job_file(file_path, args.iam_role, args.dry_run)
            
            if result['fixes_applied'] > 0:
                action = 'Would fix' if args.dry_run else 'Fixed'
                print(f"✅ {action} {result['fixes_applied']} source(s) in {result['job_name']}")
                total_fixes += result['fixes_applied']
                fixed_files += 1
            else:
                print(f"⏭️  No changes needed for {result['job_name']}")
        
        print(f"\n{'Dry run - ' if args.dry_run else ''}Summary: {total_fixes} fix(es) in {fixed_files} file(s)")
        
        if args.dry_run and total_fixes > 0:
            print("\nTo apply changes, run without --dry-run")


if __name__ == '__main__':
    main()
