#!/usr/bin/env python3
"""
VIPR Lab ORCID Publications Sync
Fetches publications from multiple ORCID profiles, deduplicates co-authored papers,
and generates Hugo-compatible markdown files.
"""

import requests
import json
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Set
import argparse
import yaml
from collections import defaultdict


class VIPRLabORCIDSync:
    def __init__(self, config_file: str, content_dir: str = "content/publication",
                 client_id: str = None, client_secret: str = None):
        self.content_dir = Path(content_dir)
        self.base_url = "https://pub.orcid.org/v3.0"
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        
        # Load lab configuration
        with open(config_file, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.lab_members = self.config.get('lab_members', [])
        self.naming_convention = self.config.get('naming_convention', 'firstauthor-year')
        
        # Track publications by DOI to avoid duplicates
        self.publications_by_doi = {}
        self.publications_without_doi = []
        
        # Get access token if credentials provided
        if self.client_id and self.client_secret:
            self._get_access_token()
    
    def _get_access_token(self):
        """Get access token using client credentials"""
        token_url = "https://orcid.org/oauth/token"
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'client_credentials',
            'scope': '/read-public'
        }
        headers = {'Accept': 'application/json'}
        
        print("Obtaining access token...")
        response = requests.post(token_url, data=data, headers=headers)
        response.raise_for_status()
        
        token_data = response.json()
        self.access_token = token_data.get('access_token')
        print("✅ Access token obtained\n")
    
    def fetch_member_works(self, orcid_id: str, member_name: str) -> List[Dict]:
        """Fetch all works from a single ORCID profile"""
        url = f"{self.base_url}/{orcid_id}/works"
        headers = {"Accept": "application/json"}
        
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        
        print(f"Fetching works for {member_name} ({orcid_id})...")
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            works = []
            
            if "group" in data:
                for group in data["group"]:
                    if "work-summary" in group:
                        work_summary = group["work-summary"][0]
                        # Add member info to the work
                        work_summary['fetched_for_member'] = member_name
                        work_summary['fetched_for_orcid'] = orcid_id
                        works.append(work_summary)
            
            print(f"  Found {len(works)} works\n")
            return works
            
        except Exception as e:
            print(f"  ❌ Error fetching works: {e}\n")
            return []
    
    def fetch_work_details(self, orcid_id: str, put_code: str) -> Optional[Dict]:
        """Fetch detailed information for a specific work"""
        url = f"{self.base_url}/{orcid_id}/work/{put_code}"
        headers = {"Accept": "application/json"}
        
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return None
    
    def extract_metadata(self, work_detail: Dict, fetched_for_member: str) -> Dict:
        """Extract relevant metadata from ORCID work detail"""
        metadata = {
            "title": "",
            "authors": [],
            "publication_date": "",
            "year": "",
            "journal": "",
            "doi": "",
            "url": "",
            "abstract": "",
            "publication_type": "",
            "put_code": work_detail.get("put-code", ""),
            "fetched_for_member": fetched_for_member,
            "lab_member_authors": []  # Will store which lab members are authors
        }
        
        # Extract title
        if "title" in work_detail and work_detail["title"]:
            if "title" in work_detail["title"] and work_detail["title"]["title"]:
                metadata["title"] = work_detail["title"]["title"].get("value", "")
        
        # Extract publication date
        if "publication-date" in work_detail and work_detail["publication-date"]:
            pub_date = work_detail["publication-date"]
            year = pub_date.get("year", {}).get("value", "")
            month = pub_date.get("month", {}).get("value", "01")
            day = pub_date.get("day", {}).get("value", "01")
            
            if year:
                metadata["year"] = str(year)
                month = str(month).zfill(2) if month else "01"
                day = str(day).zfill(2) if day else "01"
                metadata["publication_date"] = f"{year}-{month}-{day}"
        
        # Extract journal/publication name
        if "journal-title" in work_detail and work_detail["journal-title"]:
            metadata["journal"] = work_detail["journal-title"].get("value", "")
        
        # Extract DOI and URLs
        if "external-ids" in work_detail and work_detail["external-ids"]:
            if "external-id" in work_detail["external-ids"]:
                for ext_id in work_detail["external-ids"]["external-id"]:
                    if ext_id.get("external-id-type") == "doi":
                        doi_value = ext_id.get("external-id-value", "")
                        # Normalize DOI (remove any prefix)
                        doi_value = doi_value.replace("https://doi.org/", "").replace("http://doi.org/", "")
                        metadata["doi"] = doi_value
                        metadata["url"] = f"https://doi.org/{doi_value}"
        
        # Extract publication type
        if "type" in work_detail:
            metadata["publication_type"] = work_detail["type"]
        
        # Extract contributors/authors
        if "contributors" in work_detail and work_detail["contributors"]:
            if "contributor" in work_detail["contributors"]:
                for contributor in work_detail["contributors"]["contributor"]:
                    if "credit-name" in contributor and contributor["credit-name"]:
                        author_name = contributor["credit-name"]["value"]
                        metadata["authors"].append(author_name)
                        
                        # Check if this author is a lab member
                        for member in self.lab_members:
                            # Simple name matching (could be improved)
                            if member['name'].lower() in author_name.lower():
                                metadata["lab_member_authors"].append(member['name'])
        
        return metadata
    
    def create_slug(self, metadata: Dict) -> str:
        """Create a URL-friendly slug based on lab naming convention"""
        title = metadata["title"]
        year = metadata["year"]
        authors = metadata["authors"]
        
        # Get first author's last name
        first_author_slug = "unknown"
        if authors:
            first_author = authors[0]
            # Try to extract last name (assumes "First Last" format)
            name_parts = first_author.split()
            if name_parts:
                first_author_slug = name_parts[-1].lower()
                # Remove any non-alphanumeric characters
                first_author_slug = re.sub(r'[^\w\s-]', '', first_author_slug)
        
        # Build slug based on convention
        if self.naming_convention == "firstauthor-year":
            slug = f"{first_author_slug}-{year}" if year else first_author_slug
        elif self.naming_convention == "firstauthor-et-al-year":
            if len(authors) > 1:
                slug = f"{first_author_slug}-et-al-{year}" if year else f"{first_author_slug}-et-al"
            else:
                slug = f"{first_author_slug}-{year}" if year else first_author_slug
        else:
            # firstauthor-shortname-year
            short_title = title.lower()
            short_title = re.sub(r'[^\w\s-]', '', short_title)
            short_title = re.sub(r'[-\s]+', '-', short_title)
            short_title = short_title[:30]  # Limit length
            slug = f"{first_author_slug}-{short_title}-{year}" if year else f"{first_author_slug}-{short_title}"
        
        # Clean up and limit length
        slug = slug.strip('-')
        slug = slug[:60]  # Max length
        
        return slug
    
    def work_exists(self, slug: str) -> bool:
        """Check if a publication already exists in Hugo content"""
        pub_dir = self.content_dir / slug
        return pub_dir.exists() and (pub_dir / "index.md").exists()
    
    def generate_hugo_frontmatter(self, metadata: Dict) -> str:
        """Generate Hugo Academic theme frontmatter for a publication"""
        # Map ORCID publication types to Hugo Academic types
        type_mapping = {
            "journal-article": "2",
            "book": "5",
            "book-chapter": "6",
            "conference-paper": "1",
            "preprint": "3",
            "report": "4",
        }
        
        pub_type = type_mapping.get(metadata["publication_type"].lower(), "0")
        
        # Build frontmatter dictionary
        frontmatter = {
            "title": metadata["title"],
            "authors": metadata["authors"],
            "date": metadata["publication_date"],
            "publishDate": metadata["publication_date"],
            "publication_types": [pub_type],
            "publication": metadata["journal"],
            "abstract": metadata["abstract"],
            "featured": False,
            "doi": metadata["doi"],
            "url_pdf": "",
            "url_code": "",
            "url_dataset": "",
            "url_poster": "",
            "url_project": "",
            "url_slides": "",
            "url_source": "",
            "url_video": "",
        }
        
        # Add lab member tags
        if metadata["lab_member_authors"]:
            frontmatter["tags"] = [f"lab-member:{name.lower().replace(' ', '-')}" 
                                   for name in metadata["lab_member_authors"]]
        
        # Add DOI link if available
        if metadata["doi"]:
            frontmatter["links"] = [
                {"name": "DOI", "url": f"https://doi.org/{metadata['doi']}"}
            ]
        
        # Convert to YAML
        yaml_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False, 
                            allow_unicode=True, width=1000)
        
        return f"---\n{yaml_str}---\n"
    
    def create_publication_file(self, metadata: Dict, dry_run: bool = False) -> Optional[str]:
        """Create a new Hugo publication markdown file"""
        slug = self.create_slug(metadata)
        
        # Check if already exists
        if self.work_exists(slug):
            return None
        
        if dry_run:
            return slug
        
        # Create directory
        pub_dir = self.content_dir / slug
        pub_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate content
        frontmatter = self.generate_hugo_frontmatter(metadata)
        
        # Create index.md
        index_file = pub_dir / "index.md"
        with open(index_file, "w", encoding="utf-8") as f:
            f.write(frontmatter)
            f.write("\n")
            if metadata["abstract"]:
                f.write(metadata["abstract"])
                f.write("\n")
        
        return slug
    
    def sync(self, dry_run: bool = False) -> Dict:
        """Main sync function for lab publications"""
        print("=" * 70)
        print("VIPR Lab ORCID Publications Sync")
        print("=" * 70)
        print()
        
        results = {
            "total_works": 0,
            "unique_publications": 0,
            "duplicates_found": 0,
            "new_publications": [],
            "existing_publications": [],
            "errors": [],
            "works_by_member": {}
        }
        
        # Fetch works from all lab members
        all_works = []
        for member in self.lab_members:
            member_name = member['name']
            orcid_id = member['orcid']
            
            works = self.fetch_member_works(orcid_id, member_name)
            results["works_by_member"][member_name] = len(works)
            all_works.extend(works)
        
        results["total_works"] = len(all_works)
        print(f"Total works fetched from all members: {results['total_works']}\n")
        print("-" * 70)
        print("Processing and deduplicating...\n")
        
        # Process each work and deduplicate
        for i, work_summary in enumerate(all_works, 1):
            try:
                put_code = work_summary.get("put-code")
                orcid_id = work_summary.get('fetched_for_orcid')
                member_name = work_summary.get('fetched_for_member')
                
                title = work_summary.get("title", {}).get("title", {}).get("value", "Unknown")
                
                # Fetch detailed information
                work_detail = self.fetch_work_details(orcid_id, put_code)
                
                if not work_detail:
                    error_msg = f"Could not fetch details for work {put_code} ({member_name})"
                    results["errors"].append(error_msg)
                    continue
                
                # Extract metadata
                metadata = self.extract_metadata(work_detail, member_name)
                
                if not metadata["title"]:
                    error_msg = f"No title found for work {put_code} ({member_name})"
                    results["errors"].append(error_msg)
                    continue
                
                # Check for duplicate by DOI
                doi = metadata["doi"]
                if doi:
                    if doi in self.publications_by_doi:
                        # Duplicate found - add this member to the list of authors
                        existing = self.publications_by_doi[doi]
                        if member_name not in existing["lab_member_authors"]:
                            existing["lab_member_authors"].append(member_name)
                        results["duplicates_found"] += 1
                        print(f"[{i}/{len(all_works)}] ⚡ Duplicate: {title[:60]}... "
                              f"(also by {member_name})")
                        continue
                    else:
                        # New unique publication
                        self.publications_by_doi[doi] = metadata
                else:
                    # No DOI - harder to deduplicate, but add anyway
                    self.publications_without_doi.append(metadata)
                
                results["unique_publications"] += 1
                
                # Create slug and check if exists
                slug = self.create_slug(metadata)
                
                if self.work_exists(slug):
                    results["existing_publications"].append(slug)
                    print(f"[{i}/{len(all_works)}] ⏭️  Already exists: {slug}")
                    continue
                
                # Create new publication (unless dry run)
                created_slug = self.create_publication_file(metadata, dry_run=dry_run)
                if created_slug:
                    results["new_publications"].append(created_slug)
                    status = "🔍 Would create" if dry_run else "✅ Created"
                    print(f"[{i}/{len(all_works)}] {status}: {created_slug}")
                
            except Exception as e:
                error_msg = f"Error processing work {put_code} ({member_name}): {str(e)}"
                print(f"[{i}/{len(all_works)}] ❌ {error_msg}")
                results["errors"].append(error_msg)
        
        # Print summary
        print("\n" + "=" * 70)
        print("SYNC SUMMARY")
        print("=" * 70)
        print(f"\nWorks fetched by member:")
        for member, count in results["works_by_member"].items():
            print(f"  {member}: {count}")
        print(f"\nTotal works fetched: {results['total_works']}")
        print(f"Unique publications (after deduplication): {results['unique_publications']}")
        print(f"Co-authored papers (duplicates removed): {results['duplicates_found']}")
        print(f"New publications created: {len(results['new_publications'])}")
        print(f"Existing publications: {len(results['existing_publications'])}")
        print(f"Errors: {len(results['errors'])}")
        
        if results["new_publications"]:
            print(f"\n📝 New publications {'(would be created)' if dry_run else ''}:")
            for slug in results["new_publications"][:10]:  # Show first 10
                print(f"  - {slug}")
            if len(results["new_publications"]) > 10:
                print(f"  ... and {len(results['new_publications']) - 10} more")
        
        if results["errors"]:
            print(f"\n⚠️  Errors encountered:")
            for error in results["errors"][:10]:  # Show first 10
                print(f"  - {error}")
            if len(results["errors"]) > 10:
                print(f"  ... and {len(results['errors']) - 10} more")
        
        return results


def main():
    parser = argparse.ArgumentParser(
        description="Sync VIPR Lab publications from multiple ORCID profiles"
    )
    parser.add_argument(
        "--config",
        default="lab_config.yaml",
        help="Path to lab configuration file"
    )
    parser.add_argument(
        "--content-dir",
        default="content/publication",
        help="Path to Hugo publication content directory"
    )
    parser.add_argument(
        "--client-id",
        help="ORCID Public API Client ID"
    )
    parser.add_argument(
        "--client-secret",
        help="ORCID Public API Client Secret"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be created without actually creating files"
    )
    
    args = parser.parse_args()
    
    # Initialize syncer
    syncer = VIPRLabORCIDSync(
        config_file=args.config,
        content_dir=args.content_dir,
        client_id=args.client_id,
        client_secret=args.client_secret
    )
    
    # Run sync
    results = syncer.sync(dry_run=args.dry_run)
    
    # Exit with error code if there were errors
    if results["errors"]:
        exit(1)


if __name__ == "__main__":
    main()
