# This file is part of Snagboot
# Copyright (C) 2023 Bootlin
#
# Written by Romain Gantois <romain.gantois@bootlin.com> in 2023.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""
High Assurance Boot event codes from HAB4 API reference manual
"""

status_codes = {
0x00: "HAB_STS_ANY",
0x33: "HAB_FAILURE",
0x69: "HAB_WARNING",
0xf0: "HAB_SUCCESS"
}

reason_codes = {
0x00: "HAB_RSN_ANY",
0x30: "HAB_ENG_FAIL",
0x22: "HAB_INV_ADDRESS",
0x0c: "HAB_INV_ASSERTION",
0x28: "HAB_INV_CALL",
0x21: "HAB_INV_CERTIFICATE",
0x06: "HAB_INV_COMMAND",
0x11: "HAB_INV_CSF",
0x27: "HAB_INV_DCD",
0x0f: "HAB_INV_INDEX",
0x05: "HAB_INV_IVT",
0x1d: "HAB_INV_KEY",
0x1e: "HAB_INV_RETURN",
0x18: "HAB_INV_SIGNATURE",
0x17: "HAB_INV_SIZE",
0x2e: "HAB_MEM_FAIL",
0x2b: "HAB_OVR_COUNT",
0x2d: "HAB_OVR_STORAGE",
0x12: "HAB_UNS_ALGORITHM",
0x03: "HAB_UNS_COMMAND",
0x0a: "HAB_UNS_ENGINE",
0x24: "HAB_UNS_ITEM",
0x1b: "HAB_UNS_KEY",
0x14: "HAB_UNS_PROTOCOL",
0x09: "HAB_UNS_STATE"
}

context_codes = {
0x00: "HAB_CTX_ANY",
0xe1: "HAB_CTX_ENTRY",
0x33: "HAB_CTX_TARGET",
0x0a: "HAB_CTX_AUTHENTICATE",
0xdd: "HAB_CTX_DCD",
0xcf: "HAB_CTX_CSF",
0xc0: "HAB_CTX_COMMAND",
0xdb: "HAB_CTX_AUT_DAT",
0xa0: "HAB_CTX_ASSERT",
0xee: "HAB_CTX_EXIT"
}

engine_tags = {
0x00: "HAB_ENG_ANY",
0x03: "HAB_ENG_SCC",
0x05: "HAB_ENG_RTIC",
0x06: "HAB_ENG_SAHARA",
0x0a: "HAB_ENG_CSU",
0x0c: "HAB_ENG_SRTC",
0x1b: "HAB_ENG_DCP",
0x1d: "HAB_ENG_CAAM",
0x1e: "HAB_ENG_SNVS",
0x21: "HAB_ENG_OCOTP",
0x22: "HAB_ENG_DTCP",
0x36: "HAB_ENG_ROM",
0x24: "HAB_ENG_HDCP",
0xff: "HAB_ENG_SW"
}
