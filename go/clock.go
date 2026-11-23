package flowsemantics

import "time"

// Clock is the injected clock abstraction (SPEC 6.1, 6.2). Wall is epoch ms;
// Monotonic is a process-relative millisecond counter.
type Clock interface {
	// Wall returns wall-clock time in epoch milliseconds.
	Wall() int64
	// Monotonic returns monotonic time in milliseconds (process-relative).
	Monotonic() int64
}

// SystemClock is the default clock backed by the system clock (SPEC 6.3).
type SystemClock struct{}

// Wall returns wall-clock time in epoch milliseconds.
func (SystemClock) Wall() int64      { return time.Now().UnixMilli() }
// Monotonic returns monotonic time in milliseconds since process start.
func (SystemClock) Monotonic() int64 { return time.Since(processStart).Milliseconds() }

var processStart = time.Now()

// FakeClock is a deterministic clock for tests and replay (SPEC 6.2, 12.10).
type FakeClock struct {
	wallMs int64
	monoMs int64
}

// NewFakeClock creates a FakeClock with fixed wall (epoch ms) and monotonic (ms) values.
func NewFakeClock(wall, mono int64) *FakeClock {
	return &FakeClock{wallMs: wall, monoMs: mono}
}

// Wall returns the current wall time in epoch milliseconds.
func (c *FakeClock) Wall() int64      { return c.wallMs }
// Monotonic returns the current monotonic time in milliseconds.
func (c *FakeClock) Monotonic() int64 { return c.monoMs }
// Advance moves both wall and monotonic clocks forward by the given milliseconds.
func (c *FakeClock) Advance(ms int64) { c.wallMs += ms; c.monoMs += ms }
