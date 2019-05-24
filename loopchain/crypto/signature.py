# Copyright 2018 ICON Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
""" A class for icx authorization of Peer"""

import binascii
import getpass
import hashlib
import logging
from typing import Union, Type, TypeVar
from asn1crypto import keys
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from secp256k1 import Base, ALL_FLAGS, PrivateKey, PublicKey

T = TypeVar('T', bound='SignVerifier')


class SignVerifier:
    _base = Base(None, ALL_FLAGS)
    _pri = PrivateKey(ctx=_base.ctx)

    def __init__(self):
        self.address: str = None

    def verify_address(self, pubkey: bytes):
        new_address = self.address_from_pubkey(pubkey)
        if new_address != self.address:
            raise RuntimeError(f"Address is not valid."
                               f"Address({new_address}), "
                               f"Expected({self.address}")

    def verify_data(self, origin_data: bytes, signature: bytes):
        self.verify_signature(origin_data, signature, False)

    def verify_hash(self, origin_data: bytes, signature):
        self.verify_signature(origin_data, signature, True)

    def verify_signature(self, origin_data: bytes, signature: bytes, is_hash: bool):
        try:
            origin_signature, recover_code = signature[:-1], signature[-1]
            recoverable_sig = self._pri.ecdsa_recoverable_deserialize(origin_signature, recover_code)
            pub = self._pri.ecdsa_recover(origin_data,
                                          recover_sig=recoverable_sig,
                                          raw=is_hash,
                                          digest=hashlib.sha3_256)
            extract_pub = PublicKey(pub, ctx=self._base.ctx).serialize(compressed=False)
            return self.verify_address(extract_pub)
        except Exception as e:
            raise RuntimeError(f"signature verification fail : {origin_data} {signature}\n"
                               f"{e}")

    @classmethod
    def address_from_pubkey(cls, pubkey: bytes):
        hash_pub = hashlib.sha3_256(pubkey[1:]).hexdigest()
        return f"hx{hash_pub[-40:]}"

    @classmethod
    def address_from_prikey(cls, prikey: Union[bytes, PrivateKey]):
        prikey = prikey if isinstance(prikey, PrivateKey) else PrivateKey(prikey)
        pubkey = prikey.pubkey.serialize(compressed=False)
        return cls.address_from_pubkey(pubkey)

    @classmethod
    def from_address(cls: Type[T], address: str) -> T:
        verifier = SignVerifier()
        verifier.address = address
        return verifier

    @classmethod
    def from_channel(cls: Type[T], channel: str) -> T:
        from loopchain import configure as conf

        if 'public_path' in conf.CHANNEL_OPTION[channel]:
            logging.warning(f"This setting(public_path) will be deprecated soon. "
                            f"Please refer to the key configuration guide.")
            public_file = conf.CHANNEL_OPTION[channel]['public_path']
        else:
            public_file = conf.PUBLIC_PATH
        return cls.from_pubkey_file(public_file)

    @classmethod
    def from_pubkey_file(cls: Type[T], pubkey_file: str) -> T:
        with open(pubkey_file, "rb") as file:
            public_bytes = file.read()
        if pubkey_file.endswith('.der'):
            temp_public = serialization.load_der_public_key(public_bytes, default_backend())
        elif pubkey_file.endswith('.pem'):
            temp_public = serialization.load_pem_public_key(public_bytes, default_backend())
        else:
            raise RuntimeError(f"Not supported file {pubkey_file}")

        temp_public = temp_public.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        key_info = keys.PublicKeyInfo.load(temp_public)
        pubkey = key_info['public_key'].native
        return cls.from_pubkey(pubkey)

    @classmethod
    def from_pubkey(cls: Type[T], pubkey: bytes) -> T:
        address = cls.address_from_pubkey(pubkey)
        return cls.from_address(address)

    @classmethod
    def from_prikey_file(cls: Type[T], prikey_file: str, password: Union[str, bytes]) -> T:
        if isinstance(password, str):
            password = password.encode()

        if prikey_file.endswith('.der') or prikey_file.endswith('.pem'):
            with open(prikey_file, "rb") as file:
                private_bytes = file.read()
            try:
                if prikey_file.endswith('.der'):
                    temp_private = serialization \
                        .load_der_private_key(private_bytes,
                                              password,
                                              default_backend())
                elif prikey_file.endswith('.pem'):
                    temp_private = serialization \
                        .load_pem_private_key(private_bytes,
                                              password,
                                              default_backend())
                else:
                    raise RuntimeError("Cannot be here.")
            except Exception as e:
                raise ValueError("Invalid Password(Peer Certificate load test)")
            else:
                no_pass_private = temp_private.private_bytes(
                    encoding=serialization.Encoding.DER,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                )
                key_info = keys.PrivateKeyInfo.load(no_pass_private)
                prikey = long_to_bytes(key_info['private_key'].native['private_key'])
        else:
            from tbears.libs.icx_signer import key_from_key_store
            prikey = key_from_key_store(prikey_file, password)
        return cls.from_prikey(prikey)

    @classmethod
    def from_prikey(cls: Type[T], prikey: bytes) -> T:
        address = cls.address_from_prikey(prikey)
        return cls.from_address(address)


class Signer(SignVerifier):
    def __init__(self):
        super().__init__()
        self._private_key: PrivateKey = None

    def sign_data(self, data):
        return self.sign(data, False)

    def sign_hash(self, data):
        return self.sign(data, True)

    def sign(self, data, is_hash: bool):
        if is_hash:
            if isinstance(data, str):
                try:
                    data = data.split("0x")[1] if data.startswith("0x") else data
                    data = binascii.unhexlify(data)
                except Exception as e:
                    logging.error(f"hash data must hex string or bytes \n exception : {e}")
                    return None

        if not isinstance(data, (bytes, bytearray)):
            logging.error(f"data must be bytes \n")
            return None

        raw_sig = self._private_key.ecdsa_sign_recoverable(msg=data,
                                                           raw=is_hash,
                                                           digest=hashlib.sha3_256)
        serialized_sig, recover_id = self._private_key.ecdsa_recoverable_serialize(raw_sig)
        return serialized_sig + bytes((recover_id, ))

    @classmethod
    def from_address(cls: Type[T], address: str) -> T:
        raise TypeError("Cannot create `Signer` from address")

    @classmethod
    def from_channel(cls: Type[T], channel: str) -> T:
        from loopchain import configure as conf

        if 'private_path' in conf.CHANNEL_OPTION[channel]:
            logging.warning(f"This setting(private_path) will be deprecated soon. "
                            f"Please refer to the key configuration guide.")
            prikey_file = conf.CHANNEL_OPTION[channel]['private_path']
        else:
            prikey_file = conf.PRIVATE_PATH

        if 'private_password' in conf.CHANNEL_OPTION[channel]:
            logging.warning(f"This setting(private_password) will be deprecated soon. "
                            f"Please refer to the key configuration guide.")
            password = conf.CHANNEL_OPTION[channel]['private_password']
        elif conf.PRIVATE_PASSWORD:
            password = conf.PRIVATE_PASSWORD
        else:
            # created the private key file from tbears.
            password = getpass.getpass(f"Input your keystore password for channel({channel}): ")
        return cls.from_prikey_file(prikey_file, password)

    @classmethod
    def from_pubkey(cls: Type[T], pubkey: bytes) -> T:
        raise TypeError("Cannot create `Signer` from pubkey")

    @classmethod
    def from_pubkey_file(cls: Type[T], pubkey_file: str) -> T:
        raise TypeError("Cannot create `Signer` from pubkey file")

    @classmethod
    def from_prikey_file(cls: Type[T], prikey_file: str, password: Union[str, bytes]) -> T:
        return super().from_prikey_file(prikey_file, password)

    @classmethod
    def from_prikey(cls: Type[T], prikey: Union[bytes, PrivateKey]):
        auth = Signer()
        auth._private_key = prikey if isinstance(prikey, PrivateKey) else PrivateKey(prikey, ctx=cls._base.ctx)
        auth.address = cls.address_from_prikey(prikey)

        # verify
        sign = auth.sign_data(b'TEST')
        try:
            auth.verify_data(b'TEST', sign)
        except:
            raise ValueError("Invalid Signature(Peer Certificate load test)")
        return auth


def long_to_bytes(val, endianness='big'):
    """
    Use :ref:`string formatting` and :func:`~binascii.unhexlify` to
    convert ``val``, a :func:`long`, to a byte :func:`str`.

    :param long val: The value to pack

    :param str endianness: The endianness of the result. ``'big'`` for
      big-endian, ``'little'`` for little-endian.

    If you want byte- and word-ordering to differ, you're on your own.

    Using :ref:`string formatting` lets us use Python's C innards.
    """

    # one (1) hex digit per four (4) bits
    width = val.bit_length()

    # unhexlify wants an even multiple of eight (8) bits, but we don't
    # want more digits than we need (hence the ternary-ish 'or')
    width += 8 - ((width % 8) or 8)

    # format width specifier: four (4) bits per hex digit
    fmt = '%%0%dx' % (width // 4)

    # prepend zero (0) to the width, to zero-pad the output
    s = binascii.unhexlify(fmt % val)

    if endianness == 'little':
        # see http://stackoverflow.com/a/931095/309233
        s = s[::-1]

    return s
