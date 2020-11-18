#!/bin/sh
set -x

PLOT="python3 ar6_wg3_ch10 plot"

$PLOT --ar6-data="world" 1
$PLOT --ar6-data="R5" 1
$PLOT --ar6-data="R10" 1
$PLOT --ar6-data="country" 1

$PLOT --ar6-data="world" 2
$PLOT --ar6-data="R5" 2
$PLOT --ar6-data="R10" 2
$PLOT --ar6-data="country" 2

$PLOT --ar6-data="world" 4
$PLOT --ar6-data="R5" 4
$PLOT --ar6-data="R10" 4
$PLOT --ar6-data="country" 4

$PLOT --ar6-data="world" 5
$PLOT --ar6-data="R5" 5
$PLOT --ar6-data="R10" 5
$PLOT --ar6-data="country" 5

$PLOT --ar6-data="world" 6
$PLOT --ar6-data="R5" 6
$PLOT --ar6-data="R10" 6
$PLOT --ar6-data="country" 6

# # Variants for M.Craig
# for ss in world R5 R10 country
# do
#   for recat in A B
#   do
#     for bw in 5 8 9
#     do
#       $PLOT --ar6-data="$ss" --recategorize="$recat" --bandwidth="$bw" 6
#     done
#   done
# done
