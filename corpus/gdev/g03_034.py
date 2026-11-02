# task: Calculate the Kullback-Leibler divergence between two fixed discrete probability distributions and print it in nats.
import math


def kl_divergence(p: list[float], q: list[float]) -> float:
    """Return D_KL(P || Q) in nats for discrete distributions P and Q.

    Terms with p_i == 0 contribute 0 by convention. If p_i > 0 while q_i == 0,
    the divergence is infinite.
    """
    if len(p) != len(q):
        raise ValueError("distributions must have the same length")
    total = 0.0
    for pi, qi in zip(p, q):
        if pi == 0.0:
            continue
        if qi == 0.0:
            return math.inf
        total += pi * math.log(pi / qi)
    return total


def normalize(weights: list[float]) -> list[float]:
    s = sum(weights)
    if s <= 0:
        raise ValueError("weights must sum to a positive value")
    return [w / s for w in weights]


def main() -> None:
    p: list[float] = normalize([0.10, 0.40, 0.50])
    q: list[float] = normalize([0.80, 0.15, 0.05])

    d_pq = kl_divergence(p, q)
    d_qp = kl_divergence(q, p)

    print(f"P = {p}")
    print(f"Q = {q}")
    print(f"D_KL(P || Q) = {d_pq:.6f} nats")
    print(f"D_KL(Q || P) = {d_qp:.6f} nats")


if __name__ == "__main__":
    main()
