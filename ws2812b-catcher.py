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
        self.cd_sys.clk = clk12
        sys150 = Signal()

        pll_locked_unbuffered = Signal()
        pll_locked_led = platform.request("user_led", 1)
        pll_locked = Signal()

        self.comb += [
            pll_locked_led.eq(pll_locked)
        ]

        self.specials += [
            Instance("SB_PLL40_CORE",        
                p_FEEDBACK_PATH="SIMPLE",
                p_PLLOUT_SELECT="GENCLK",
                p_DIVR=0,
                p_DIVF=79,
                p_DIVQ=4,
                p_FILTER_RANGE=1,

                i_BYPASS=0, i_RESETB=1,
                i_REFERENCECLK=clk12,

                o_PLLOUTGLOBAL=sys150,
                o_LOCK=pll_locked_unbuffered
            ),
            Instance("SB_GB", i_USER_SIGNAL_TO_GLOBAL_BUFFER=sys150, o_GLOBAL_BUFFER_OUTPUT=self.cd_sys150.clk),
            Instance("SB_GB", i_USER_SIGNAL_TO_GLOBAL_BUFFER=pll_locked_unbuffered, o_GLOBAL_BUFFER_OUTPUT=pll_locked),
        ]

class IceStickSpecCatcherPlatform(Platform):
    def __init__(self):
        Platform.__init__(self)

        self.add_extension([
            ("rgbled", 0, Pins("44"), IOStandard("LVCMOS33")),
            ("rawclock", 0, Pins("45"), IOStandard("LVCMOS33")),
        ])

class WS2812bPhy(Module):
    def __init__(self, rgbled):
        pixel_bit = Signal(5, reset=24)
        pixel_num = Signal(5, reset=4)
        max_pixels = Signal(5, reset=2)
        delay_counter = Signal(32, reset=0)
        pixel = Signal(24, reset=0xffffff)
        current_pixel = Signal(24)
        do_hi = Signal()
        delay_counter_reload = Signal(24)

        clk_freq = 60000000
        T0H = int(0.000400 * clk_freq)
        T1H = int(0.000800 * clk_freq)
        T0L = int(0.000850 * clk_freq)
        T1L = int(0.000450 * clk_freq)
        RES = int(0.5 * clk_freq)

        self.sync.sys150 += [
            If(delay_counter,
                delay_counter.eq(delay_counter - 1)
            ).Elif(pixel_bit >= 24,
#                rgbled.eq(0),

                pixel_bit.eq(0),
                current_pixel.eq(pixel),

                # If we've run out of pixels on the chain, issue a reset.
                If(pixel_num >= max_pixels,
                    delay_counter.eq(RES),
                    pixel_num.eq(0),
                ).Else(
                    delay_counter.eq(1)
                )
                # Otherwise, move on to the next pixel and start over
                # ).Else(
                #     pixel_num.eq(pixel_num + 1),
                #     rgbled.eq(1),

                #     If(pixel[0],
                #         delay_counter.eq(T1H)
                #     ).Else(
                #         delay_counter.eq(T0H)
                #     )
                # )
            # WS2812b is a Hi followed by a Lo.
            ).Elif(do_hi,
                do_hi.eq(0),
                rgbled.eq(1),
                If(current_pixel[0],
                    delay_counter.eq(T1H)
                ).Else(
                    delay_counter.eq(T0H)
                )
            ).Else(
                do_hi.eq(1),
                rgbled.eq(0),
                pixel_bit.eq(pixel_bit + 1),
                current_pixel.eq(current_pixel >> 1),
                If(current_pixel[0],
                    delay_counter.eq(T1L)
                ).Else(
                    delay_counter.eq(T0L)
                )
            )
        ]

class WS2812bSpecCatcher(Module):
    def __init__(self, platform):
        led = platform.request("user_led")
        rgbled = platform.request("rgbled")
        counter = Signal(26)
        rawclock = platform.request("rawclock")

        self.submodules.ClockGen = ClockGen(platform)
        self.submodules.LEDGenerator = WS2812bPhy(rgbled)
        self.comb += led.eq(counter[25])
        self.comb += rawclock.eq(counter[0])
        self.sync.sys150 += counter.eq(counter + 1)

def main():
    platform = IceStickSpecCatcherPlatform()
    top = WS2812bSpecCatcher(platform)
    platform.build(top)

if __name__ == "__main__":
    main()
