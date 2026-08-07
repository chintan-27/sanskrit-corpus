#!/usr/bin/env bash
#SBATCH --account=neurology-dept
#SBATCH --partition=hpg-default
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=12:00:00
#SBATCH --job-name=ia-quality
#SBATCH --output=/blue/neurology-dept/chintan.acharya/sanskrit-corpus/data/logs/ia_quality_%j.log
#SBATCH --error=/blue/neurology-dept/chintan.acharya/sanskrit-corpus/data/logs/ia_quality_%j.log

set -euo pipefail
cd /blue/neurology-dept/chintan.acharya/sanskrit-corpus
srun bash scripts/run_ia_quality.sh
