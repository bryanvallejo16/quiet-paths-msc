#!/bin/bash -l
#SBATCH -J graph_noise_test
#SBATCH -o graph_noise_test_out.txt
#SBATCH -e graph_noise_test_err.txt
#SBATCH -n 1
#SBATCH --nodes=1
#SBATCH --cpus-per-task=10
#SBATCH --mem-per-cpu=2000
#SBATCH -t 00:04:00
#SBATCH –p test
#SBATCH --mail-type=END
#

export OMP_NUM_THREADS=10
module load geoconda
srun python graph_noise_test.py
