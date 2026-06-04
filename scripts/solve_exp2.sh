
echo "Job started on $(hostname) at $(date)"
cd ~/combinationProblemGeneration
# uv sync -U
nohup uv run solve.py --threads 10 \
             --timeout 2000.0 \
             --memory 40480.0 \
             --output combEval/exp_2_solved_depth_4_constraint_1 \
             --problems data/exp_2_problems_depth_4_constraint_1 > "logs/solve-$(date +%Y%m%d_%H%M%S).log" 2>&1 &
echo "Job ended at $(date)"