
echo "Job started on $(hostname) at $(date)"
cd ~/combinationProblemGeneration
# uv sync -U
nohup uv run solve.py --threads 50 \
             --timeout 2000.0 \
             --memory 40480.0 \
             --output combEval/exp_3_problems_solved \
             --problems data/exp_3 > "logs/solve-$(date +%Y%m%d_%H%M%S).log" 2>&1 &
echo "Job ended at $(date)"