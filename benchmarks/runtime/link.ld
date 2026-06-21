ENTRY(_start)

MEMORY
{
  IMEM (rx)  : ORIGIN = 0x00000000, LENGTH = 128K
  DMEM (rwx) : ORIGIN = 0x00010000, LENGTH = 128K
}

SECTIONS
{
  .text : ALIGN(4) {
    *(.text.startup*)
    *(.text*)
  } > IMEM

  .data : ALIGN(4) {
    . = ORIGIN(DMEM) + 0x100;
    *(.rodata*)
    *(.srodata*)
    *(.data*)
    *(.sdata*)
  } > DMEM

  .bss (NOLOAD) : ALIGN(4) {
    __bss_start = .;
    *(.sbss*)
    *(.bss*)
    *(COMMON)
    __bss_end = .;
  } > DMEM

  PROVIDE(__stack_top = ORIGIN(DMEM) + LENGTH(DMEM) - 256);
}
