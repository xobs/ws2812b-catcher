#!/usr/bin/env python3
# This variable defines all the external programs that this module
# relies on.  lxbuildenv reads this variable in order to ensure
# the build will finish without exiting due to missing third-party
# programs.
LX_DEPENDENCIES = ["yosys", "arachne-pnr"]

# Import lxbuildenv to integrate the deps/ directory
import lxbuildenv

from migen import *
from litex.boards.platforms.icestick import Platform
from litex.build.generic_platform import Pins, IOStandard

class ClockGen(Module):
    def __init__(self, platform):
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_sys150 = ClockDomain(reset_less=True)

        clk12 = platform.request("clk12")
        rst = Signal()
        #self.clk50 = Signal()

        self.specials += [
            Instance("SB_PLL40_CORE",        
                p_FEEDBACK_PATH="SIMPLE",
                p_PLLOUT_SELECT="GENCLK",
                p_DIVR=0,
                p_DIVF=49,
                p_DIVQ=2,
                p_FILTER_RANGE=1,

                i_BYPASS=0, i_RESETB=1,
                i_REFERENCECLK=clk12, o_PLLOUTCORE=self.cd_sys150.clk,
            ),
        ]

class IceStickSpecCatcherPlatform(Platform):
    def __init__(self):
        Platform.__init__(self)

        self.add_extension([
            ("rgbled", 0, Pins("44"), IOStandard("LVCMOS33"))
        ])

class WS2812bPhy(Module):
    def __init__(self, rgbled):
        pixel_bit = Signal(5)
        pixel_num = Signal(32)
        max_pixels = Signal(32)
        delay_counter = Signal(32)
        pixel = Signal(24, reset=0xff00ff)
        lo_or_hi = Signal()

        clk_freq = 150000000
        T0H = int(0.000400 * clk_freq)
        T1H = int(0.000800 * clk_freq)
        T0L = int(0.000850 * clk_freq)
        T1L = int(0.000450 * clk_freq)
        RES = int(0.000250 * clk_freq)

        self.sync += [
            If(delay_counter > 0,
                delay_counter.eq(delay_counter - 1)
            ).Else(
                If(pixel_bit >= 24,
                    If(pixel_num >= max_pixels,
                        pixel_num.eq(0),
                        lo_or_hi.eq(0),
                        delay_counter.eq(RES)
                    ).Else(
                        pixel_num.eq(pixel_num + 1),
                        lo_or_hi.eq(1),
                        If(pixel[pixel_num + 1],
                            rgbled.eq(0),
                            delay_counter.eq(T0H)
                        ).Else(
                            rgbled.eq(1),
                            delay_counter.eq(T1H)
                        )
                    )
                ).Elif(lo_or_hi,
                    lo_or_hi.eq(0),
                    pixel_num.eq(pixel_num + 1),
                    If(pixel[pixel_num],
                        rgbled.eq(0),
                        delay_counter.eq(T0L)
                    ).Else(
                        rgbled.eq(1),
                        delay_counter.eq(T1L)
                    )
                ).Else(
                    lo_or_hi.eq(1),
                    If(pixel[pixel_num],
                        rgbled.eq(0),
                        delay_counter.eq(T0H)
                    ).Else(
                        rgbled.eq(1),
                        delay_counter.eq(T1H)
                    )
                )
            )
        ]

class WS2812bSpecCatcher(Module):
    def __init__(self, platform):
        led = platform.request("user_led")
        rgbled = platform.request("rgbled")
        counter = Signal(26)


        self.submodules.ClockGen = ClockGen(platform)
        self.submodules.LEDGenerator = WS2812bPhy(rgbled)
        self.comb += led.eq(counter[25])
        self.sync.sys150 += counter.eq(counter + 1)

def main():
    platform = IceStickSpecCatcherPlatform()
    top = WS2812bSpecCatcher(platform)
    platform.build(top)

if __name__ == "__main__":
    main()
