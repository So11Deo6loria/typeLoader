# typeLoader

typeLoader is a Ghidra script that can aid in reverse engineering bare metal firmware. It relies on vendor specific types used for the hardware abstraction layer (HAL). Currently it only partially supports STM32 libraries but I am working on improving the support and making it more scalable. Please reach out to me if you would like to support in any way: So11Deo6loria@proton.me. 

# Usage
The script can be loaded into Ghidra and invoked at any point during the RE process. Once the types are added you can simply cast variables as pointers to the added types. I also plan to explore automatically suggesting types at some point. 
3ew![typeLoaderDemo](https://github.com/So11Deo6loria/typeLoader/assets/14260835/afa93db9-573e-4f7e-901e-ae67312ff5c1)
