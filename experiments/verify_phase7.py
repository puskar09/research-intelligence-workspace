import subprocess
import sys
import os

def main():
    print("Running Phase 7 Verification...")
    
    # Check if dataset exists
    if not os.path.exists("evaluation/dataset.json"):
        print("ERROR: evaluation/dataset.json not found.")
        sys.exit(1)
        
    # Check if run_evaluation.py exists
    if not os.path.exists("experiments/run_evaluation.py"):
        print("ERROR: experiments/run_evaluation.py not found.")
        sys.exit(1)
        
    # Run the evaluation script
    print("Executing experiments/run_evaluation.py...")
    result = subprocess.run(
        [sys.executable, "experiments/run_evaluation.py"],
        capture_output=False,
        text=True
    )
    
    if result.returncode != 0:
        print("ERROR: Evaluation script failed.")
        sys.exit(1)
        
    # Check if results were saved
    if not os.path.exists("evaluation/results/phase7_results.json"):
        print("ERROR: evaluation/results/phase7_results.json not created.")
        sys.exit(1)
        
    if not os.path.exists("evaluation/results/phase7_results.csv"):
        print("ERROR: evaluation/results/phase7_results.csv not created.")
        sys.exit(1)
        
    print("Phase 7 Verification Successful.")
    sys.exit(0)

if __name__ == "__main__":
    main()
