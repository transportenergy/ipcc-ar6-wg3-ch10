#!/bin/sh
set -x

# Add --skip-cache here when the initial data-loading code changes
PLOT="python3 ar6_wg3_ch10 plot"

for fig in 1 2 4 5 6 7; do
for ss in world R5 R10 country; do
for recat in "" "--recategorize=A" "--recategorize=B"; do

# Add --per-capita here, e.g. for fig_2
$PLOT --ar6-data="$ss" $recat $fig

# # fig_6 variants for M.Craig. --bandwidth=8 is default, so don't repeat
# for bw in 5 9; do
#
# $PLOT --ar6-data="$ss" $recat --bandwidth="$bw" 6
#
# done

done
done
done
