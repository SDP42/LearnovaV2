# Sorting Algorithms

## Why sorting matters
Sorting puts data into order so that searching, merging and reporting become faster. Binary search, for example, needs a sorted array and finds an item in O(log n) steps instead of O(n).

## Bubble sort
Bubble sort repeatedly compares neighbouring items and swaps them if they are in the wrong order. After each pass the largest remaining item has moved to the end. It is simple but slow, with O(n^2) time in the average and worst case.

## Merge sort
Merge sort is a divide and conquer algorithm. It splits the array into halves, sorts each half recursively, and then merges the two sorted halves. Its running time is O(n log n) in every case, but it needs O(n) extra memory.

## Quick sort
Quick sort chooses a pivot, partitions the items into those smaller and larger than the pivot, and sorts each part recursively. The average time is O(n log n), whereas the worst case is O(n^2) when the pivot is chosen badly. It sorts in place, so it uses little extra memory.

## Comparing the algorithms
Bubble sort is O(n^2) and stable, and it is used for teaching. Merge sort is O(n log n) and stable, and it suits linked lists and external sorting. Quick sort is O(n log n) on average and not stable, and it is usually fastest in practice.

## Choosing an algorithm
If memory is tight, use quick sort. If you need stability or guaranteed speed, use merge sort. For tiny inputs, simple methods are fine. Python's built-in sort uses Timsort, a hybrid that combines merge sort and insertion sort.
