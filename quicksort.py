"""
快速排序（QuickSort）实现
=========================

快速排序是一种高效的排序算法，采用分治思想：
1. 选择基准元素（pivot）
2. 分区：小于基准的放左边，大于基准的放右边
3. 递归排序左右子数组

时间复杂度：
    - 平均 O(n log n)
    - 最坏 O(n²)（当数组已经有序时）

空间复杂度：
    - 原地版本 O(log n)（递归栈空间）
    - 非原地版本 O(n)

稳定性：不稳定
"""

from __future__ import annotations

import random
from typing import Any, List, TypeVar

T = TypeVar("T")


# =============================================================
# 版本一：经典原地分区法（最推荐，生产环境常用）
# =============================================================


def quicksort_inplace(arr: List[T], left: int = 0, right: int | None = None) -> None:
    """原地快速排序，直接修改原数组。

    使用 Lomuto 分区方案，随机选择基准以避免最坏情况。

    Args:
        arr: 待排序列表
        left: 左边界索引（含）
        right: 右边界索引（含），默认为 len(arr)-1
    """
    if right is None:
        right = len(arr) - 1

    if left >= right:
        return

    # 分区，返回基准元素的最终位置
    pivot_idx = _partition_random(arr, left, right)

    # 递归排序左右两部分
    quicksort_inplace(arr, left, pivot_idx - 1)
    quicksort_inplace(arr, pivot_idx + 1, right)


def _partition(arr: List[T], left: int, right: int) -> int:
    """Lomuto 分区方案。

    以 arr[right] 为基准，将数组分为两部分：
    - [left..i]  <= pivot
    - [i+1..right-1] > pivot
    - arr[right] = pivot（最终位置）

    Returns:
        基准元素的最终索引
    """
    pivot = arr[right]
    i = left - 1  # i 指向最后一个 <= pivot 的元素

    for j in range(left, right):
        if arr[j] <= pivot:
            i += 1
            arr[i], arr[j] = arr[j], arr[i]

    # 把基准放到正确位置
    arr[i + 1], arr[right] = arr[right], arr[i + 1]
    return i + 1


def _partition_random(arr: List[T], left: int, right: int) -> int:
    """随机选择基准的 Lomuto 分区。

    随机选取一个元素与 arr[right] 交换，避免有序数组导致 O(n²)。
    """
    rand_idx = random.randint(left, right)
    arr[rand_idx], arr[right] = arr[right], arr[rand_idx]
    return _partition(arr, left, right)


# =============================================================
# 版本二：Hoare 分区法（比 Lomuto 更高效）
# =============================================================


def quicksort_hoare(arr: List[T], left: int = 0, right: int | None = None) -> None:
    """使用 Hoare 分区方案的快速排序。

    Hoare 分区通常比 Lomuto 做更少的交换，效率更高。

    Args:
        arr: 待排序列表
        left: 左边界索引（含）
        right: 右边界索引（含）
    """
    if right is None:
        right = len(arr) - 1

    if left >= right:
        return

    pivot_idx = _partition_hoare(arr, left, right)

    # Hoare 分区返回的是基准的位置，但基准不一定在中间
    # 左右两边都包含 pivot_idx
    quicksort_hoare(arr, left, pivot_idx)
    quicksort_hoare(arr, pivot_idx + 1, right)


def _partition_hoare(arr: List[T], left: int, right: int) -> int:
    """Hoare 分区方案。

    选择中间元素为基准，从两端向中间扫描并交换逆序对。
    """
    pivot = arr[(left + right) // 2]
    i, j = left, right

    while True:
        while arr[i] < pivot:
            i += 1
        while arr[j] > pivot:
            j -= 1
        if i >= j:
            return j
        arr[i], arr[j] = arr[j], arr[i]
        i += 1
        j -= 1


# =============================================================
# 版本三：简洁版（非原地，适合教学理解）
# =============================================================


def quicksort_simple(arr: List[T]) -> List[T]:
    """简洁的快速排序（非原地）。

    更容易理解，但会创建新列表，空间复杂度 O(n log n)。

    Args:
        arr: 待排序列表

    Returns:
        排序后的新列表

    Examples:
        >>> quicksort_simple([3, 6, 8, 10, 1, 2, 1])
        [1, 1, 2, 3, 6, 8, 10]
    """
    if len(arr) <= 1:
        return arr

    pivot = arr[len(arr) // 2]

    # 三次遍历，很直观
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]

    return quicksort_simple(left) + middle + quicksort_simple(right)


# =============================================================
# 版本四：三路快排（处理大量重复元素）
# =============================================================


def quicksort_3way(arr: List[T], left: int = 0, right: int | None = None) -> None:
    """三路快速排序。

    将数组分为三部分：< pivot, == pivot, > pivot。
    适用于大量重复元素的场景。

    Args:
        arr: 待排序列表
        left: 左边界索引（含）
        right: 右边界索引（含）
    """
    if right is None:
        right = len(arr) - 1

    if left >= right:
        return

    lt, gt = _partition_3way(arr, left, right)

    quicksort_3way(arr, left, lt - 1)
    quicksort_3way(arr, gt + 1, right)


def _partition_3way(arr: List[T], left: int, right: int) -> tuple[int, int]:
    """三路分区。

    维护三个区域：
    - [left..lt-1] < pivot
    - [lt..gt] == pivot
    - [gt+1..right] > pivot

    Returns:
        (lt, gt) 等于 pivot 的左右边界
    """
    # 随机选择基准
    rand_idx = random.randint(left, right)
    arr[rand_idx], arr[right] = arr[right], arr[rand_idx]
    pivot = arr[right]

    lt = left   # lt 指向第一个 == pivot 的元素
    gt = right  # gt 指向最后一个 == pivot 的元素
    i = left

    while i <= gt:
        if arr[i] < pivot:
            arr[lt], arr[i] = arr[i], arr[lt]
            lt += 1
            i += 1
        elif arr[i] > pivot:
            arr[gt], arr[i] = arr[i], arr[gt]
            gt -= 1
        else:
            i += 1

    return lt, gt


# =============================================================
# 辅助函数
# =============================================================


def is_sorted(arr: List[Any]) -> bool:
    """检查列表是否已排序（升序）。"""
    return all(arr[i] <= arr[i + 1] for i in range(len(arr) - 1))


# =============================================================
# 测试与演示
# =============================================================


def demo() -> None:
    """演示各种快速排序的实现。"""
    print("=" * 60)
    print("快速排序演示")
    print("=" * 60)

    # 测试数据
    test_cases = [
        [3, 6, 8, 10, 1, 2, 1],
        [5, 5, 5, 5, 5],
        [1],
        [],
        [9, 8, 7, 6, 5, 4, 3, 2, 1],
        [random.randint(0, 100) for _ in range(10)],
    ]

    for i, data in enumerate(test_cases, 1):
        print(f"\n测试用例 {i}: {data}")

        # 原地排序（随机 Lomuto）
        arr1 = data.copy()
        quicksort_inplace(arr1)
        print(f"  原地快排 (Lomuto): {arr1} (有序: {is_sorted(arr1)})")

        # Hoare 分区
        arr2 = data.copy()
        quicksort_hoare(arr2)
        print(f"  Hoare 快排:         {arr2} (有序: {is_sorted(arr2)})")

        # 简洁版
        arr3 = quicksort_simple(data)
        print(f"  简洁版快排:          {arr3} (有序: {is_sorted(arr3)})")

        # 三路快排
        arr4 = data.copy()
        quicksort_3way(arr4)
        print(f"  三路快排 (重复元素): {arr4} (有序: {is_sorted(arr4)})")

    # 性能对比
    print("\n" + "=" * 60)
    print("性能测试（n = 10000）")
    print("=" * 60)

    import time

    n = 10000
    data = [random.randint(0, n) for _ in range(n)]

    for name, sort_fn in [
        ("原地快排 (Lomuto)", lambda: quicksort_inplace(data.copy())),
        ("Hoare 快排", lambda: quicksort_hoare(data.copy())),
        ("简洁版快排", lambda: quicksort_simple(data.copy())),
        ("三路快排", lambda: quicksort_3way(data.copy())),
        ("Python 内置排序 (Timsort)", lambda: sorted(data)),
    ]:
        start = time.perf_counter()
        sort_fn()
        elapsed = time.perf_counter() - start
        print(f"  {name:.<25} {elapsed:.4f} 秒")


if __name__ == "__main__":
    demo()
