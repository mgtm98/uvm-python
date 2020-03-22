#//
#// -------------------------------------------------------------
#//    Copyright 2004-2011 Synopsys, Inc.
#//    Copyright 2010 Mentor Graphics Corporation
#//    Copyright 2010-2011 Cadence Design Systems, Inc.
#//    Copyright 2019-2020 Tuomas Poikela (tpoikela)
#//    All Rights Reserved Worldwide
#//
#//    Licensed under the Apache License, Version 2.0 (the
#//    "License"); you may not use this file except in
#//    compliance with the License.  You may obtain a copy of
#//    the License at
#//
#//        http://www.apache.org/licenses/LICENSE-2.0
#//
#//    Unless required by applicable law or agreed to in
#//    writing, software distributed under the License is
#//    distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
#//    CONDITIONS OF ANY KIND, either express or implied.  See
#//    the License for the specific language governing
#//    permissions and limitations under the License.
#// -------------------------------------------------------------
#//


import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge

from uvm import (UVMConfigDb, run_test, UVMCoreService, sv,
    uvm_fatal, UVMUtils, uvm_hdl)
from uvm.seq.uvm_sequence import UVMSequence
from uvm.macros import *
from uvm.base.uvm_config_db import *
from uvm.reg.uvm_reg_model import *

from apb.apb_if import apb_if
from tb_env import tb_env


class dut_reset_seq(UVMSequence):

    def __init__(self, name="dut_reset_seq"):
        super().__init__(name)
        self.dut_top = None


    async def body(self):
        self.dut_top.rst = 1
        for _ in range(5):
            await FallingEdge(self.dut_top.apb_pclk)
        self.dut_top.rst = 0


uvm_object_utils(dut_reset_seq)


class FIFORegTest(tb_env):

    def __init__(self, name="FIFORegTest", parent=None):
        super().__init__(name, parent)


    async def run_phase(self, phase):
        status = 0x0
        data = 0x0
        expected = []
        max_val = 0
        FIFO = None  # fifo_reg
        regmodel = self.regmodel

        dut = []
        UVMConfigDb.get(None, "DUT_REF", "dut", dut)
        dut = dut[0]

        phase.raise_objection(self)

        uvm_info("Test", "Resetting DUT and Register Model...", UVM_LOW)
        rst_seq = dut_reset_seq.type_id.create("rst_seq", self)
        rst_seq.dut_top = dut
        await rst_seq.start(None)
        regmodel.reset()

        FIFO = regmodel.FIFO
        max_val = FIFO.capacity()
        FIFO.set_compare(UVM_CHECK)

        uvm_info("FIFO Example",
            sv.sformatf("Initializing FIFO reg of max_val size %0d with set()...",max_val), UVM_LOW)

        expected = [0] * max_val

        # SET - preload regmodel; remodel now has full FIFO; DUT still empty
        for i in range(len(expected)):
            data = sv.urandom()
            expected[i] = data
            FIFO.set(data)


        uvm_info("FIFO Example",
            sv.sformatf("Updating DUT FIFO reg with mirror using update()..."), UVM_LOW)

        # UPDATE - write regmodel contents to DUT; DUT now has full FIFO
        status = []
        await FIFO.update(status)
        if status[0] == UVM_NOT_OK:
            uvm_fatal("FIFO Update Error", "Received status UVM_NOT_OK updating DUT")


        uvm_info("FIFO Example",
            sv.sformatf(" Read back DUT FIFO reg into mirror using read()..."), UVM_LOW)

        # READ - read contents of DUT back to regmodel; DUT is empty now, regmodel FULL
        for i in range(len(expected)):
            status = []
            data = []
            await FIFO.read(status, data)
            if status[0] == UVM_NOT_OK:
                uvm_fatal("FIFO Read Error", "Received status UVM_NOT_OK updating Regmodel")

        phase.drop_objection(self)



@cocotb.test()
async def test_reg_fifo(dut):
    cs_ = UVMCoreService.get()
    test = FIFORegTest("test")
    svr = cs_.get_report_server()
    svr.set_max_quit_count(10)
    vif = apb_if(dut)

    UVMConfigDb.set(test, "apb", "vif", vif)
    UVMConfigDb.set(None, "DUT_REF", "dut", dut)

    cocotb.fork(Clock(vif.clk, 10, "NS").start())
    await run_test(dut=dut)
