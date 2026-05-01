import threading
import random
import queue
import sys

# ── Queues simulating communication channel ───────────────────────────────────
p2s = queue.Queue()   # Primary → Secondary
s2p = queue.Queue()   # Secondary → Primary

# ── Bit counter ───────────────────────────────────────────────────────────────
bits_sent = 0
bits_lock = threading.Lock()

def send(q, msg, bits=0):
    global bits_sent
    with bits_lock:
        bits_sent += bits
    q.put(msg)

def log_bits(label, b):
    global bits_sent
    with bits_lock:
        bits_sent += b
    print(f"[BITS] {label}: {b} bits  (total so far: {bits_sent})")

# ── Helpers ───────────────────────────────────────────────────────────────────
def is_prime(n):
    if n < 2: return False
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0: return False
    return True

def primes_in_range(lo, hi):
    return [n for n in range(lo, hi + 1) if is_prime(n)]

def random_prime(lo, hi):
    pool = primes_in_range(lo, hi)
    if not pool:
        raise ValueError(f"No primes found in [{lo}, {hi}]")
    return random.choice(pool)

def quarter(x, m):
    """Which quarter of [0, 2^m) does x fall in? Returns 0,1,2,3"""
    size = (2 ** m) // 4
    return min(x // size, 3)

def bit_at(x, pos):
    """Return the bit of x at position pos (0-indexed from LSB)"""
    return (x >> pos) & 1

def bits_needed(n):
    """Minimum bits to represent n"""
    return max(1, n.bit_length())

# ── Input ─────────────────────────────────────────────────────────────────────
def get_input(m):
    print("\n╔══════════════════════════════════════════╗")
    print("║     Las Vegas String Matching Algorithm  ║")
    print("╚══════════════════════════════════════════╝\n")
    print(f"Each string is an integer in [0, 2^{m} - 1] = [0, {2**m - 1}]")
    print("Press ENTER to randomize all values.\n")

    choice = input("Manual input? (y/n): ").strip().lower()
    if choice != 'y':
        U = [random.randint(0, 2**m - 1) for _ in range(10)]
        V = [random.randint(0, 2**m - 1) for _ in range(10)]
        # Plant a match for demo
        idx = random.randint(0, 9)
        V[idx] = U[idx]
        print(f"\n[SETUP] Randomized. Match planted at index {idx}.")
        return U, V

    print("\nEnter 10 integers for U (Primary), space-separated:")
    U = list(map(int, input("U: ").split()))
    print("Enter 10 integers for V (Secondary), space-separated:")
    V = list(map(int, input("V: ").split()))

    if len(U) != 10 or len(V) != 10:
        print("Need exactly 10 values each. Exiting.")
        sys.exit(1)

    max_val = 2**m - 1
    if any(x < 0 or x > max_val for x in U + V):
        print(f"All values must be in [0, {max_val}]. Exiting.")
        sys.exit(1)

    return U, V

# ── Primary Thread ────────────────────────────────────────────────────────────
def primary(U, m):
    run = 0
    while True:
        run += 1
        print(f"\n{'═'*55}")
        print(f"  RUN {run}")
        print(f"{'═'*55}")

        # ── Round 1: prime p + fingerprints + random bit probe ────────────────
        p = random_prime(m * m, 2 * m * m)
        bit_pos = random.randint(0, m - 1)   # random bit position to probe

        fingerprints_p = [u % p for u in U]
        bit_probes     = [bit_at(u, bit_pos) for u in U]

        print(f"\n[PRIMARY] Round 1:")
        print(f"          Prime p       = {p}")
        print(f"          Bit position  = {bit_pos}  (probing bit {bit_pos} of each string)")
        print(f"          Fingerprints  = {fingerprints_p}")
        print(f"          Bit probes    = {bit_probes}")

        # Cost: log2(p) + log2(m) + 10*(log2(p) + 1)
        bits_p          = bits_needed(p)
        bits_bitpos     = bits_needed(bit_pos)          # log2(m) to encode position
        bits_fps        = 10 * bits_needed(p)           # 10 fingerprints
        bits_bps        = 10 * 1                        # 10 single bits
        round1_bits     = bits_p + bits_bitpos + bits_fps + bits_bps
        log_bits("Round 1 (p + bit_pos + 10 fingerprints + 10 bit probes)", round1_bits)

        send(p2s, ("R1", p, bit_pos, fingerprints_p, bit_probes))

        # ── Receive K after Round 1 ───────────────────────────────────────────
        msg = s2p.get()
        if msg[0] == "NO_MATCH":
            print(f"\n[PRIMARY] ✗ Output: NO — no k with uₖ = vₖ exists.")
            return
        if msg[0] == "FOUND":
            k, verified = msg[1], msg[2]
            status = "✓ YES" if verified else "✗ NO MATCH (false positive)"
            print(f"\n[PRIMARY] {status} at k={k}")
            if verified: return
            print(f"[PRIMARY] Restarting...\n")
            continue

        K1 = msg[1]   # ("CANDIDATES_R1", K1)

        # ── Round 2: second prime q + quarter info for survivors ──────────────
        q = random_prime(2 * m * m + 1, 4 * m * m)    # distinct range from p
        fingerprints_q = [U[k] % q for k in K1]
        quarters_u     = [quarter(U[k], m) for k in K1]

        print(f"\n[PRIMARY] Round 2 (|K1|={len(K1)} candidates: {K1}):")
        print(f"          Prime q        = {q}")
        print(f"          Fingerprints q = {fingerprints_q}")
        print(f"          Quarters       = {quarters_u}")

        bits_q      = bits_needed(q)
        bits_fps_q  = len(K1) * bits_needed(q)
        bits_qrtrs  = len(K1) * 2                      # 2 bits per quarter
        round2_bits = bits_q + bits_fps_q + bits_qrtrs
        log_bits(f"Round 2 (q + {len(K1)} fingerprints + {len(K1)} quarters)", round2_bits)

        send(p2s, ("R2", q, fingerprints_q, quarters_u, K1))

        # ── Receive final candidate ───────────────────────────────────────────
        msg = s2p.get()
        if msg[0] == "NO_MATCH":
            print(f"\n[PRIMARY] ✗ Output: NO — no k with uₖ = vₖ exists.")
            return
        if msg[0] == "FOUND":
            k, verified = msg[1], msg[2]
            status = "✓ YES" if verified else "✗ NO MATCH (false positive)"
            print(f"\n[PRIMARY] {status} at k={k}")
            if verified: return
            print(f"[PRIMARY] Restarting...\n")
            continue

        K2 = msg[1]   # ("CANDIDATES_R2", K2)

        # ── Round 3: pick random survivor, send full m-bit string ─────────────
        k_star = random.choice(K2)
        print(f"\n[PRIMARY] Round 3: K2={K2}, picked k*={k_star}, sending full u[{k_star}]={U[k_star]}")
        log_bits(f"Round 3 (full {m}-bit string u[{k_star}])", m)

        send(p2s, ("R3", k_star, U[k_star]))

        # ── Receive verdict ───────────────────────────────────────────────────
        verdict = s2p.get()
        if verdict[0] == "YES":
            print(f"\n[PRIMARY] ✓ Output: YES — u[{k_star}] = v[{k_star}]")
            return
        else:
            print(f"\n[PRIMARY] False positive at k*={k_star}. Restarting...\n")

# ── Secondary Thread ──────────────────────────────────────────────────────────
def secondary(V, m):
    while True:
        # ── Round 1 ───────────────────────────────────────────────────────────
        msg = p2s.get()
        p, bit_pos, fps_p, bps = msg[1], msg[2], msg[3], msg[4]

        print(f"\n[SECONDARY] Round 1: received p={p}, bit_pos={bit_pos}")

        K1 = [k for k in range(10)
              if V[k] % p == fps_p[k] and bit_at(V[k], bit_pos) == bps[k]]

        print(f"[SECONDARY] K1 (after fingerprint + bit probe) = {K1}")

        if not K1:
            send(s2p, ("NO_MATCH",))
            print(f"[SECONDARY] K1 empty → NO_MATCH")
            return

        if len(K1) == 1:
            # Lucky — only one candidate, skip round 2
            k = K1[0]
            print(f"[SECONDARY] Only one candidate k={k}, skip Round 2.")
            send(s2p, ("FOUND", k, None))   # Primary doesn't verify here; go to round 3 directly
            # Actually: request full string via normal flow
            send(s2p, ("CANDIDATES_R1", K1))
        else:
            send(s2p, ("CANDIDATES_R1", K1))

        # ── Round 2 ───────────────────────────────────────────────────────────
        msg = p2s.get()
        if msg[0] != "R2":
            continue
        q, fps_q, quarters_u, K1_echo = msg[1], msg[2], msg[3], msg[4]

        print(f"\n[SECONDARY] Round 2: received q={q}")

        K2 = []
        for i, k in enumerate(K1_echo):
            vk_mod_q  = V[k] % q
            vk_qtr    = quarter(V[k], m)
            if vk_mod_q == fps_q[i] and vk_qtr == quarters_u[i]:
                K2.append(k)

        print(f"[SECONDARY] K2 (after 2nd fingerprint + quarter check) = {K2}")

        if not K2:
            send(s2p, ("NO_MATCH",))
            print(f"[SECONDARY] K2 empty → NO_MATCH")
            return

        send(s2p, ("CANDIDATES_R2", K2))

        # ── Round 3 ───────────────────────────────────────────────────────────
        msg = p2s.get()
        k_star, u_k = msg[1], msg[2]

        print(f"\n[SECONDARY] Round 3: received u[{k_star}]={u_k}, v[{k_star}]={V[k_star]}")

        if u_k == V[k_star]:
            send(s2p, ("YES",))
            print(f"[SECONDARY] ✓ Match confirmed at k={k_star}")
            return
        else:
            send(s2p, ("RESTART",))
            print(f"[SECONDARY] ✗ False positive at k={k_star}, restarting...")

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    m = 16   # bit length; change as needed

    U, V = get_input(m)

    print(f"\n[SETUP] m = {m}")
    print(f"[SETUP] U = {U}")
    print(f"[SETUP] V = {V}\n")

    # Check ground truth
    true_matches = [k for k in range(10) if U[k] == V[k]]
    print(f"[SETUP] True matches at indices: {true_matches if true_matches else 'None'}")

    t1 = threading.Thread(target=primary,   args=(U, m))
    t2 = threading.Thread(target=secondary, args=(V, m))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    print(f"\n{'═'*55}")
    print(f"  TOTAL BITS EXCHANGED: {bits_sent}")
    print(f"  BUDGET:  m + O(log m) = {m} + O({m.bit_length()}) ≈ {m + 10 * m.bit_length()}")
    print(f"{'═'*55}\n")