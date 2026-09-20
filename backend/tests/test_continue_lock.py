"""续写互斥锁的单元验证 —— 用假项目 id，不碰真实项目。

覆盖 2026-09-15 卡死事故的三种场景：
  A. 两个不同任务抢同一项目      → 只有一个拿到
  B. 同一 task_id 重投（worker 重启）
     → 认得自己的锁，能续期接管（旧实现会永久卡死）
  C. 上一个持有者已收工（项目状态不再是 generating）
     → takeover_ok 允许接管；未收工时即使 takeover_ok 也不该抢走
"""
import sys
import uuid

sys.path.insert(0, "/app")

from app.tasks.novel_tasks import (
    _acquire_continue_lock,
    _release_continue_lock,
    _redis_client,
    CONTINUE_LOCK_KEY,
)

PID = "lock-test-" + uuid.uuid4().hex[:8]
KEY = CONTINUE_LOCK_KEY.format(PID)
r = _redis_client()
fails = []


def check(name, got, want):
    ok = got == want
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: got={got} want={want}", flush=True)
    if not ok:
        fails.append(name)


try:
    A, B = "task-AAA", "task-BBB"

    # A. 首个任务拿到锁，第二个不同任务抢不到
    check("A1 首个任务拿到锁", _acquire_continue_lock(PID, A), True)
    check("A2 另一任务抢不到", _acquire_continue_lock(PID, B), False)

    # B. 同一个 task_id 重投 —— 必须认锁续期，而不是被自己的锁挡死
    check("B1 同 task_id 重投可接管", _acquire_continue_lock(PID, A), True)
    check("B2 重投后锁仍归自己", r.get(KEY).decode(), A)

    # C. 上一个持有者已收工（takeover_ok=True）→ 允许接管
    check("C1 已收工时允许接管", _acquire_continue_lock(PID, B, takeover_ok=True), True)
    check("C2 接管后锁易主", r.get(KEY).decode(), B)

    # D. 未收工（takeover_ok=False）→ 不许抢走
    check("D1 未收工时不可抢走", _acquire_continue_lock(PID, A, takeover_ok=False), False)
    check("D2 锁仍在原持有者手里", r.get(KEY).decode(), B)

    # E. 释放：只有持有者能释放
    _release_continue_lock(PID, A)
    check("E1 非持有者释放无效", r.get(KEY).decode(), B)
    _release_continue_lock(PID, B)
    check("E2 持有者释放成功", r.get(KEY), None)

    # F. 释放后可重新获取
    check("F1 释放后可再获取", _acquire_continue_lock(PID, A), True)
finally:
    r.delete(KEY)

print(f"\n结果: {'全部通过' if not fails else '失败 ' + str(fails)}", flush=True)
sys.exit(1 if fails else 0)
