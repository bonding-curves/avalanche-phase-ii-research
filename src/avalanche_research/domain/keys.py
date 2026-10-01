"""The key behind a signed C-Chain transaction, and that key's EVM and P-Chain addresses.

A C-Chain account and a P-Chain address belong to one key when the P-Chain address is the key's ``ripemd160(sha256(
compressed public key))`` in bech32 with the ``avax`` prefix. The public key is recovered from any transaction the
account signed: the signature ``v, r, s`` over the transaction's signing hash. This covers legacy transactions with the
chain ID in ``v`` (EIP-155) and dynamic-fee transactions (EIP-1559) with an empty access list. Pure computation, so a
result is checked by recovering the sender's EVM address and comparing it with ``from``.
"""

from __future__ import annotations

import hashlib
from typing import Any

from ..core.errors import DataError

_ROUNDS = (0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000, 0x000000000000808B,
           0x0000000080000001, 0x8000000080008081, 0x8000000000008009, 0x000000000000008A, 0x0000000000000088,
           0x0000000080008009, 0x000000008000000A, 0x000000008000808B, 0x800000000000008B, 0x8000000000008089,
           0x8000000000008003, 0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
           0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008)
_ROTATIONS = ((0, 36, 3, 41, 18), (1, 44, 10, 45, 2), (62, 6, 43, 15, 61), (28, 55, 25, 21, 56), (27, 20, 39, 8, 14))
_MASK = (1 << 64) - 1
# secp256k1
_P = 2**256 - 2**32 - 977
_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
_G = (0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
      0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8)
_BECH32 = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"


def _rotate(value: int, bits: int) -> int:
    return ((value << bits) | (value >> (64 - bits))) & _MASK if bits else value


def _permute(state: list[list[int]]) -> list[list[int]]:
    for constant in _ROUNDS:
        column = [state[x][0] ^ state[x][1] ^ state[x][2] ^ state[x][3] ^ state[x][4] for x in range(5)]
        mix = [column[(x - 1) % 5] ^ _rotate(column[(x + 1) % 5], 1) for x in range(5)]
        state = [[state[x][y] ^ mix[x] for y in range(5)] for x in range(5)]
        moved = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5):
                moved[y][(2 * x + 3 * y) % 5] = _rotate(state[x][y], _ROTATIONS[x][y])
        state = [[moved[x][y] ^ (~moved[(x + 1) % 5][y] & moved[(x + 2) % 5][y]) for y in range(5)] for x in range(5)]
        state[0][0] ^= constant
    return state


def keccak256(data: bytes) -> bytes:
    """Ethereum's Keccak-256, the original padding, not SHA3-256."""
    rate = 136
    padded = bytearray(data) + b"\x01"
    while len(padded) % rate:
        padded += b"\x00"
    padded[-1] |= 0x80
    state = [[0] * 5 for _ in range(5)]
    for offset in range(0, len(padded), rate):
        block = padded[offset:offset + rate]
        for i in range(rate // 8):
            state[i % 5][i // 5] ^= int.from_bytes(block[8 * i:8 * i + 8], "little")
        state = _permute(state)
    return b"".join(state[i % 5][i // 5].to_bytes(8, "little") for i in range(4))


def _rlp(item: bytes | list[Any]) -> bytes:
    if isinstance(item, list):
        body = b"".join(_rlp(part) for part in item)
        return _length(len(body), 0xC0) + body
    if len(item) == 1 and item[0] < 0x80:
        return item
    return _length(len(item), 0x80) + item


def _length(size: int, offset: int) -> bytes:
    if size < 56:
        return bytes([offset + size])
    encoded = size.to_bytes((size.bit_length() + 7) // 8, "big")
    return bytes([offset + 55 + len(encoded)]) + encoded


def _integer(text: str) -> bytes:
    value = int(text, 16)
    return value.to_bytes((value.bit_length() + 7) // 8, "big") if value else b""


def _hex_bytes(text: str) -> bytes:
    return bytes.fromhex(text[2:]) if text and text != "0x" else b""


def _add(a: tuple[int, int] | None, b: tuple[int, int] | None) -> tuple[int, int] | None:
    if a is None:
        return b
    if b is None:
        return a
    if a[0] == b[0] and (a[1] + b[1]) % _P == 0:
        return None
    if a == b:
        slope = 3 * a[0] * a[0] * pow(2 * a[1], -1, _P) % _P
    else:
        slope = (b[1] - a[1]) * pow(b[0] - a[0], -1, _P) % _P
    x = (slope * slope - a[0] - b[0]) % _P
    return x, (slope * (a[0] - x) - a[1]) % _P


def _multiply(k: int, point: tuple[int, int] | None) -> tuple[int, int] | None:
    result = None
    while k:
        if k & 1:
            result = _add(result, point)
        point = _add(point, point)
        k >>= 1
    return result


def signing_hash(transaction: dict[str, Any]) -> tuple[int, int]:
    """The hash the sender signed, and the recovery ID, for a legacy EIP-155 or an EIP-1559 transaction."""
    chain = int(transaction["chainId"], 16)
    v = int(transaction["v"], 16)
    data = _hex_bytes(transaction["input"])
    if transaction["type"] == "0x0":
        fields = [_integer(transaction["nonce"]), _integer(transaction["gasPrice"]), _integer(transaction["gas"]),
                  _hex_bytes(transaction["to"]), _integer(transaction["value"]), data, _integer(hex(chain)), b"", b""]
        return int.from_bytes(keccak256(_rlp(fields)), "big"), v - 35 - 2 * chain
    if transaction["type"] == "0x2":
        if transaction.get("accessList"):
            raise DataError("a transaction with an access list is not supported")
        fields = [_integer(hex(chain)), _integer(transaction["nonce"]), _integer(transaction["maxPriorityFeePerGas"]),
                  _integer(transaction["maxFeePerGas"]), _integer(transaction["gas"]), _hex_bytes(transaction["to"]),
                  _integer(transaction["value"]), data, []]
        return int.from_bytes(keccak256(b"\x02" + _rlp(fields)), "big"), v
    raise DataError(f"unsupported transaction type: {transaction['type']}")


def recover_public_key(digest: int, r: int, s: int, recovery_id: int) -> tuple[int, int]:
    y = pow((r ** 3 + 7) % _P, (_P + 1) // 4, _P)
    if y % 2 != recovery_id % 2:
        y = _P - y
    point = _multiply(pow(r, -1, _N), _add(_multiply(s, (r, y)), _multiply((-digest) % _N, _G)))
    if point is None:
        raise DataError("the signature recovers no public key")
    return point


def _bech32(prefix: str, data: bytes) -> str:
    def polymod(values: list[int]) -> int:
        generators = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)
        check = 1
        for value in values:
            top = check >> 25
            check = (check & 0x1FFFFFF) << 5 ^ value
            for i in range(5):
                check ^= generators[i] if (top >> i) & 1 else 0
        return check
    accumulator = bits = 0
    words = []
    for byte in data:
        accumulator, bits = (accumulator << 8) | byte, bits + 8
        while bits >= 5:
            bits -= 5
            words.append((accumulator >> bits) & 31)
    if bits:
        words.append((accumulator << (5 - bits)) & 31)
    expanded = [ord(c) >> 5 for c in prefix] + [0] + [ord(c) & 31 for c in prefix]
    checksum = polymod(expanded + words + [0] * 6) ^ 1
    return prefix + "1" + "".join(_BECH32[x] for x in words + [(checksum >> 5 * (5 - i)) & 31 for i in range(6)])


def addresses(transaction: dict[str, Any], prefix: str = "avax") -> dict[str, str]:
    """The signer's EVM address and P-Chain address. Raises when the recovered EVM address is not the sender."""
    digest, recovery_id = signing_hash(transaction)
    x, y = recover_public_key(digest, int(transaction["r"], 16), int(transaction["s"], 16), recovery_id)
    evm = "0x" + keccak256(x.to_bytes(32, "big") + y.to_bytes(32, "big"))[-20:].hex()
    if evm != transaction["from"].lower():
        raise DataError(f"the recovered key signs for {evm}, not the sender {transaction['from']}")
    compressed = bytes([2 + (y & 1)]) + x.to_bytes(32, "big")
    return {"evm": evm, "p_chain": _bech32(prefix, hashlib.new("ripemd160", hashlib.sha256(compressed).digest()).digest())}
