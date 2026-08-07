#!/usr/bin/env bash
#SBATCH --account=neurology-dept
#SBATCH --partition=hpg-turin
#SBATCH --qos=neurology-dept
#SBATCH --gres=gpu:l4:1
#SBATCH --cpus-per-task=40
#SBATCH --mem=256G
#SBATCH --time=2-00:00:00
#SBATCH --job-name=ia-complete
#SBATCH --output=/blue/neurology-dept/chintan.acharya/sanskrit-corpus/data/logs/ia_complete_%j.log
#SBATCH --error=/blue/neurology-dept/chintan.acharya/sanskrit-corpus/data/logs/ia_complete_%j.log

set -euo pipefail
cd /blue/neurology-dept/chintan.acharya/sanskrit-corpus
srun bash scripts/run_ia_two_day_pipeline.sh
