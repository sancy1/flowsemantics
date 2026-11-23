// Clocks — SPEC.md section 6.1.

/** Injected clock abstraction (SPEC 6.1, 6.2). Wall is epoch ms; monotonic is a
 *  process-relative millisecond counter. */
export interface Clock {
  /** Wall-clock time in epoch milliseconds. */
  wall(): number;
  /** Monotonic time in milliseconds (process-relative). */
  monotonic(): number;
}

/** Default clock backed by the system clock (SPEC 6.3). */
export class SystemClock implements Clock {
  /** Wall-clock time in epoch milliseconds. */
  wall(): number { return Date.now(); }
  /** Monotonic time in milliseconds since process start. */
  monotonic(): number { return performance.now(); }
}

/** Deterministic clock for tests and replay (SPEC 6.2, 12.10). */
export class FakeClock implements Clock {
  private _wall: number;
  private _mono: number;
  /** Create a FakeClock with fixed wall (epoch ms) and monotonic (ms) values. */
  constructor(wall = 1_700_000_000_000, mono = 0) {
    this._wall = wall;
    this._mono = mono;
  }
  /** Current wall time in epoch milliseconds. */
  wall(): number { return this._wall; }
  /** Current monotonic time in milliseconds. */
  monotonic(): number { return this._mono; }
  /** Advance both wall and monotonic clocks by the given milliseconds. */
  advance(ms: number): void { this._wall += ms; this._mono += ms; }
}
