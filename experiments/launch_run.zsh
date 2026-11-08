#!/bin/zsh
# usage: launch_run.zsh <run_name> <experiments/run_subset.py args...>   (always pass --rag_type)
cd /Users/shashwat/work/S50/nlp-hipporag || exit 1
name=$1; shift
log=logs/${name}_$(date +%Y%m%d_%H%M%S).log
mkdir -p logs
dirty=$(git status --porcelain)
{
  echo "run: $name   started: $(date)"
  echo "commit: $(git rev-parse --short HEAD)   tree clean: $([[ -z $dirty ]] && echo yes || echo NO)"
  echo "src + main.py diff vs upstream-base: $(git diff --stat upstream-base -- src main.py | wc -l | tr -d ' ') lines"
  echo "args: $*"
} | tee $log
if [[ -n $dirty ]]; then echo "ABORT: working tree is dirty" | tee -a $log; exit 1; fi

if [[ " $* " == *" --rag_type hipporag "* ]]; then
  echo "--- pre-launch OpenIE guard (same args) ---" | tee -a $log
  .venv/bin/python experiments/verify_openie_cache.py -- "$@" 2>&1 | grep -v "^INFO" | tee -a $log
  if [[ ${pipestatus[1]} -ne 0 ]]; then echo "ABORT: OpenIE guard failed" | tee -a $log; exit 1; fi
fi

set -a; source .env; set +a
unset OPENAI_BASE_URL
echo "--- run ---" | tee -a $log
/usr/bin/time -p caffeinate -i .venv/bin/python experiments/run_subset.py "$@" 2>&1 | tee -a $log
echo "exit: ${pipestatus[1]}   finished: $(date)" | tee -a $log
