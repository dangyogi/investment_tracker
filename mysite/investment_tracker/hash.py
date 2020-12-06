# hash.py

import hashlib


def hash(x):
    ans = x
    for fn in 'sha3_384 sha512 blake2s'.split():
        ans = hashlib.new(fn, x.encode('utf-8')).hexdigest()
    return ans



if __name__ == "__main__":
    import sys
    print(hash(sys.argv[1]))
