
echo "Job started on $(hostname) at $(date)"
cd ~/combinationProblemGeneration
# uv sync -U
nohup uv run solve.py --threads 40 \
             --timeout 2000.0 \
             --memory 40480.0 \
             --output combEval/exp_2_depth_2_problems_solved \
             --problems data/exp_2_problems_depth_2 > "logs/solve-$(date +%Y%m%d_%H%M%S).log" 2>&1 &
echo "Job ended at $(date)"