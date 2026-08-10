#!/usr/bin/env bash
#SBATCH --account=neurology-dept
#SBATCH --partition=hpg-default
#SBATCH --qos=neurology-dept
#SBATCH --cpus-per-task=48
#SBATCH --mem=64G
#SBATCH --time=1-00:00:00
#SBATCH --job-name=ia-text
#SBATCH --output=/blue/neurology-dept/chintan.acharya/sanskrit-corpus/data/logs/ia_text_%j.log
#SBATCH --error=/blue/neurology-dept/chintan.acharya/sanskrit-corpus/data/logs/ia_text_%j.log

set -euo pipefail

repo_root=/blue/neurology-dept/chintan.acharya/sanskrit-corpus
cd "$repo_root"
srun bash scripts/run_ia_text_download.sh
