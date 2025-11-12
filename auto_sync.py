#!/usr/bin/env python3
"""
Automatic GitHub synchronization for Condition Task List Trader
Monitors changes and automatically pushes to GitHub with commit messages
"""

import os
import subprocess
import time
import logging
from datetime import datetime
from pathlib import Path
import json

class GitHubAutoSync:
    """Automated GitHub synchronization"""
    
    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path).resolve()
        self.logger = self._setup_logging()
        self.last_commit = None
        
    def _setup_logging(self):
        """Setup logging for auto-sync"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler('auto_sync.log'),
                logging.StreamHandler()
            ]
        )
        return logging.getLogger(__name__)
    
    def _run_command(self, cmd: str, check=True) -> subprocess.CompletedProcess:
        """Run git command safely"""
        try:
            result = subprocess.run(
                f"cd {self.repo_path} && {cmd}",
                shell=True,
                check=check,
                capture_output=True,
                text=True
            )
            return result
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Command failed: {cmd}")
            self.logger.error(f"Error: {e.stderr}")
            raise
    
    def check_changes(self) -> bool:
        """Check if there are uncommitted changes"""
        try:
            result = self._run_command("git status --porcelain", check=False)
            return result.stdout.strip() != ""
        except Exception as e:
            self.logger.error(f"Error checking changes: {e}")
            return False
    
    def check_unpushed_commits(self) -> bool:
        """Check if there are unpushed commits"""
        try:
            result = self._run_command("git log --oneline origin/main..HEAD", check=False)
            return result.stdout.strip() != ""
        except Exception as e:
            self.logger.error(f"Error checking unpushed commits: {e}")
            return False
    
    def stage_changes(self) -> bool:
        """Stage all changes"""
        try:
            self._run_command("git add .")
            self.logger.info("Changes staged successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error staging changes: {e}")
            return False
    
    def commit_changes(self) -> bool:
        """Commit changes with auto-generated message"""
        try:
            # Generate commit message
            commit_msg = self._generate_commit_message()
            
            self._run_command(f'git commit -m "{commit_msg}"')
            self.logger.info(f"Changes committed: {commit_msg}")
            
            self.last_commit = commit_msg
            return True
            
        except Exception as e:
            self.logger.error(f"Error committing changes: {e}")
            return False
    
    def _generate_commit_message(self) -> str:
        """Generate descriptive commit message based on changes"""
        try:
            # Get changed files
            result = self._run_command("git diff --cached --name-only")
            changed_files = result.stdout.strip().split('\n') if result.stdout.strip() else []
            
            # Analyze changes
            changes_type = []
            if any('production' in f for f in changed_files):
                changes_type.append('production')
            if any('deployment' in f for f in changed_files):
                changes_type.append('deployment')
            if any('docker' in f for f in changed_files):
                changes_type.append('docker')
            if any('health' in f for f in changed_files):
                changes_type.append('monitoring')
            if any('broker' in f for f in changed_files):
                changes_type.append('trading')
            if any('config' in f for f in changed_files):
                changes_type.append('configuration')
            
            # Get diff statistics
            diff_result = self._run_command("git diff --cached --stat")
            
            primary_type = changes_type[0] if changes_type else "general"
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
            
            commit_msg = f"Auto-sync [{primary_type}] - {timestamp}"
            
            if diff_result.stdout.strip():
                commit_msg += f"\n\n{diff_result.stdout.strip()}"
            
            return commit_msg
            
        except Exception as e:
            self.logger.error(f"Error generating commit message: {e}")
            return f"Auto-sync - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    
    def push_to_github(self) -> bool:
        """Push changes to GitHub with retry logic"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                self.logger.info(f"Pushing to GitHub (attempt {attempt + 1}/{max_retries})...")
                
                # Push with timeout handling (macOS compatible)
                push_cmd = f"cd {self.repo_path} && git push origin main"
                result = subprocess.run(
                    push_cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=60  # Total timeout
                )
                
                if result.returncode == 0:
                    self.logger.info("✅ Successfully pushed to GitHub")
                    return True
                else:
                    error_msg = result.stderr.strip()
                    self.logger.warning(f"Push attempt {attempt + 1} failed: {error_msg}")
                    
                    # Handle specific errors
                    if "timeout" in error_msg.lower():
                        self.logger.info("Network timeout, retrying...")
                        time.sleep(2 ** attempt)  # Exponential backoff
                    elif "network" in error_msg.lower():
                        self.logger.info("Network error, retrying...")
                        time.sleep(5)
                    else:
                        self.logger.error(f"Non-recoverable error: {error_msg}")
                        break
                        
            except subprocess.TimeoutExpired:
                self.logger.error(f"Push timeout on attempt {attempt + 1}")
                if attempt < max_retries - 1:
                    time.sleep(10)
                continue
            except Exception as e:
                self.logger.error(f"Unexpected error during push: {e}")
                break
        
        return False
    
    def sync_to_github(self) -> bool:
        """Complete sync workflow"""
        try:
            self.logger.info("🔄 Starting auto-sync to GitHub...")
            
            # Step 1: Check if there are changes
            if not self.check_changes() and not self.check_unpushed_commits():
                self.logger.info("✅ Repository is up to date")
                return True
            
            # Step 2: Stage changes if needed
            if self.check_changes():
                if not self.stage_changes():
                    return False
                
                # Step 3: Commit changes
                if not self.commit_changes():
                    return False
            
            # Step 4: Push to GitHub
            if self.push_to_github():
                self.logger.info("🎉 Auto-sync completed successfully")
                return True
            else:
                self.logger.error("❌ Auto-sync failed during push")
                return False
                
        except Exception as e:
            self.logger.error(f"Auto-sync workflow failed: {e}")
            return False
    
    def continuous_sync(self, interval_minutes: int = 5):
        """Run continuous auto-sync in background"""
        self.logger.info(f"🚀 Starting continuous auto-sync (check every {interval_minutes} minutes)")
        
        while True:
            try:
                self.sync_to_github()
                time.sleep(interval_minutes * 60)
            except KeyboardInterrupt:
                self.logger.info("👋 Auto-sync stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Error in continuous sync: {e}")
                time.sleep(minutes * 60)

def main():
    """Main auto-sync function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Auto-sync changes to GitHub")
    parser.add_argument("--continuous", "-c", action="store_true", 
                       help="Run continuous auto-sync in background")
    parser.add_argument("--interval", "-i", type=int, default=5,
                       help="Sync interval in minutes (default: 5)")
    parser.add_argument("--once", "-o", action="store_true",
                       help="Run sync once and exit")
    
    args = parser.parse_args()
    
    # Initialize auto-sync
    syncer = GitHubAutoSync()
    
    try:
        if args.once or not args.continuous:
            # One-time sync
            success = syncer.sync_to_github()
            exit(0 if success else 1)
        else:
            # Continuous sync
            syncer.continuous_sync(args.interval)
            
    except KeyboardInterrupt:
        print("\n👋 Auto-sync stopped")
    except Exception as e:
        print(f"❌ Auto-sync error: {e}")
        exit(1)

if __name__ == "__main__":
    main()
