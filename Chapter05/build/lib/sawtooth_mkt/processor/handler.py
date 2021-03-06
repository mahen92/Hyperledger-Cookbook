# Copyright 2016 Intel Corporation
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
# ------------------------------------------------------------------------------

import hashlib
import logging


from sawtooth_sdk.processor.handler import TransactionHandler
from sawtooth_sdk.processor.exceptions import InvalidTransaction
from sawtooth_sdk.processor.exceptions import InternalError

LOGGER = logging.getLogger(__name__)


class MktTransactionHandler(TransactionHandler):
    def __init__(self, namespace_prefix):
        self._namespace_prefix = namespace_prefix

    @property
    def family_name(self):
        return 'mkt'

    @property
    def family_versions(self):
        return ['1.0']

    @property
    def namespaces(self):
        return [self._namespace_prefix]

    def apply(self, transaction, context):

        try:
            # 1. Decode the transaction payload
            house, action, owner, signer = _unpack_transaction(transaction)
            _display("User {} house {} action {} owner {}".format(signer[:6], house, action, owner))

            # 2. Get the current state from  context
            dbowner, house_list = _get_state_data(context, self._namespace_prefix, house)
            _display("dbowner {} house list {} ".format(dbowner, house_list))

            # 3. Validate the trnasaction
            _validate_house_data(action, owner, signer, dbowner)

            # 4. Enforce entitlement, ACL
            # 5. Apply the transaction
            # Log for tutorial usage
            if action == "create":
                _display("User {} created a house {} owner {}.".format(signer[:6], house, owner))

            elif action == "transfer":
                _display("User {} transfer: {} from {} to {}\n\n".format(signer[:6], house, dbowner, owner))

            # 6. Store new state back in context
            _store_state_data(context, house_list, self._namespace_prefix, house, owner)

        except Exception as e:
            _display("Exception in apply {} \n\n".format(e))


def _unpack_transaction(transaction):
    header = transaction.header

    # The transaction signer is the player
    signer = header.signer_public_key

    try:
        # The payload is csv utf-8 encoded string
        house, action, owner = transaction.payload.decode().split(",")
    except ValueError:
        raise InvalidTransaction("Invalid payload serialization")

    _validate_transaction(house, action, owner)

    return house, action, owner, signer


def _validate_transaction(house, action, owner):
    if not house:
        raise InvalidTransaction('house is required')

    if not action:
        raise InvalidTransaction('Action is required')

    if not owner:
        raise InvalidTransaction('Owner is required')

    if action not in ('create', 'transfer'):
        raise InvalidTransaction('Invalid action: {}'.format(action))


def _validate_house_data(action, owner, signer, dbowner):
    if action == 'create':
        if dbowner is not None:
            raise InvalidTransaction('Invalid action: house already exists.')

    elif action == 'transfer':
        if dbowner is None:
            raise InvalidTransaction(
                'Invalid action: transfer requires an existing house.')

def _make_mkt_address(namespace_prefix, house):
    return namespace_prefix + \
        hashlib.sha512(house.encode('utf-8')).hexdigest()[:64]


def _get_state_data(context, namespace_prefix, house):
    # Get data from address
    state_entries = \
        context.get_state([_make_mkt_address(namespace_prefix, house)])

    # context.get_state() returns a list. If no data has been stored yet
    # at the given address, it will be empty.
    if state_entries:
        try:
            state_data = state_entries[0].data
            _display("state_data {} \n".format(state_data.decode()))
            house_list = { dbhouse: (dbowner) for dbhouse, dbowner in [ dbhouseowner.split(',') for dbhouseowner in state_data.decode().split('|') ] }
            _display("house list in db {} \n".format(house_list))
            dbowner = house_list[house]
            _display("db house {} db owner \n".format(house, dbowner))

        except ValueError:
            raise InternalError("Failed to deserialize game data.")

    else:
        house_list = {}
        dbowner = None

    return dbowner, house_list


def _store_state_data(context, house_list,
        namespace_prefix, house,
        owner):

    house_list[house] = (owner)  

    state_data = '|'.join(sorted([
        ','.join([house, owner])
        for house, (owner) in house_list.items()
    ])).encode()

    addresses = context.set_state(
        {_make_mkt_address(namespace_prefix, house): state_data})

    if len(addresses) < 1:
        raise InternalError("State Error")


def _display(msg):
    n = msg.count("\n")

    if n > 0:
        msg = msg.split("\n")
        length = max(len(line) for line in msg)
    else:
        length = len(msg)
        msg = [msg]

    # pylint: disable=logging-not-lazy
    LOGGER.debug("+" + (length + 2) * "-" + "+")
    for line in msg:
        LOGGER.debug("+ " + line.center(length) + " +")
    LOGGER.debug("+" + (length + 2) * "-" + "+")
