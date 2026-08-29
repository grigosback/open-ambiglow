/* DriverOtherAmbiglow.cpp
*
*  MIT License
*
*  Copyright (c) 2020-2026 awawa-dev
*
*  Project homesite: https://github.com/awawa-dev/HyperHDR
*
*  Permission is hereby granted, free of charge, to any person obtaining a copy
*  of this software and associated documentation files (the "Software"), to deal
*  in the Software without restriction, including without limitation the rights
*  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
*  copies of the Software, and to permit persons to whom the Software is
*  furnished to do so, subject to the following conditions:
*
*  The above copyright notice and this permission notice shall be included in all
*  copies or substantial portions of the Software.

*  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
*  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
*  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
*  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
*  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
*  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
*  SOFTWARE.
 */

#ifndef PCH_ENABLED
	#include <cstring>
#endif

#ifdef _WIN32
	#ifndef WIN32_LEAN_AND_MEAN
		#define WIN32_LEAN_AND_MEAN
	#endif
	#ifndef NOMINMAX
		#define NOMINMAX
	#endif
	#include <windows.h>
#else
	#include <dlfcn.h>
#endif

#include <led-drivers/other/DriverOtherAmbiglow.h>

namespace
{
	// Philips Evnia monitors: the ENE MCU on the monitor's internal USB hub
	constexpr int DEFAULT_VENDOR_ID = 0x0CF2;
	constexpr int DEFAULT_PRODUCT_ID = 0xA201;

	// Vendor interface: no endpoints, control transfers only
	constexpr int DEFAULT_INTERFACE = 0;

	// EC address of the source colour buffer, one RGB triplet per LED
	constexpr uint32_t DEFAULT_ADDRESS = 0xC450;

	constexpr uint8_t  REQ_TYPE_WRITE = 0x40;
	constexpr uint8_t  REQ_WRITE = 0x80;
	constexpr unsigned TIMEOUT_MS = 1000;

#ifdef _WIN32
	constexpr auto* LIBUSB_CANON = "libusb-1.0.dll";
	constexpr auto* LIBUSB_ALT = "libusb-1.0.dll";
#elif __APPLE__
	constexpr auto* LIBUSB_CANON = "libusb-1.0.dylib";
	constexpr auto* LIBUSB_ALT = "libusb.dylib";
#else
	constexpr auto* LIBUSB_CANON = "libusb-1.0.so.0";
	constexpr auto* LIBUSB_ALT = "libusb-1.0.so";
#endif
}

#ifdef _WIN32
	#define DYN_OPEN(name)          reinterpret_cast<void*>(LoadLibraryA(name))
	#define DYN_SYM(handle, name)   reinterpret_cast<void*>(GetProcAddress(reinterpret_cast<HMODULE>(handle), name))
	#define DYN_CLOSE(handle)       FreeLibrary(reinterpret_cast<HMODULE>(handle))
#else
	#define DYN_OPEN(name)          dlopen(name, RTLD_NOW | RTLD_LOCAL)
	#define DYN_SYM(handle, name)   dlsym(handle, name)
	#define DYN_CLOSE(handle)       dlclose(handle)
#endif

#define LOAD_PROC(UsbProc) \
if (!error && ((_fun_##UsbProc = reinterpret_cast<PTR_##UsbProc>(DYN_SYM(_dllHandle, #UsbProc))) == nullptr)) \
{ \
	error = true; \
	Error(_log, "Unable to load the " #UsbProc " procedure"); \
}

DriverOtherAmbiglow::DriverOtherAmbiglow(const QJsonObject& deviceConfig)
	: LedDevice(deviceConfig)
	, _dllHandle(nullptr)
	, _usbContext(nullptr)
	, _deviceHandle(nullptr)
	, _vendorId(DEFAULT_VENDOR_ID)
	, _productId(DEFAULT_PRODUCT_ID)
	, _interface(DEFAULT_INTERFACE)
	, _address(DEFAULT_ADDRESS)
	, _fun_libusb_init(nullptr)
	, _fun_libusb_exit(nullptr)
	, _fun_libusb_open_device_with_vid_pid(nullptr)
	, _fun_libusb_close(nullptr)
	, _fun_libusb_set_auto_detach_kernel_driver(nullptr)
	, _fun_libusb_claim_interface(nullptr)
	, _fun_libusb_release_interface(nullptr)
	, _fun_libusb_control_transfer(nullptr)
	, _fun_libusb_error_name(nullptr)
{
}

DriverOtherAmbiglow::~DriverOtherAmbiglow()
{
	close();
	unloadLibrary();
}

LedDevice* DriverOtherAmbiglow::construct(const QJsonObject& deviceConfig)
{
	return new DriverOtherAmbiglow(deviceConfig);
}

bool DriverOtherAmbiglow::loadLibrary()
{
	if (_dllHandle != nullptr)
	{
		return true;
	}

	_dllHandle = DYN_OPEN(LIBUSB_CANON);
	if (_dllHandle == nullptr)
	{
		_dllHandle = DYN_OPEN(LIBUSB_ALT);
	}

	if (_dllHandle == nullptr)
	{
		Error(_log, "Unable to load {:s} nor {:s}. Please install libusb.", LIBUSB_CANON, LIBUSB_ALT);
		return false;
	}

	bool error = false;

	LOAD_PROC(libusb_init);
	LOAD_PROC(libusb_exit);
	LOAD_PROC(libusb_open_device_with_vid_pid);
	LOAD_PROC(libusb_close);
	LOAD_PROC(libusb_claim_interface);
	LOAD_PROC(libusb_release_interface);
	LOAD_PROC(libusb_control_transfer);
	LOAD_PROC(libusb_error_name);

	// Not present on every platform (Windows builds of libusb omit it); optional.
	_fun_libusb_set_auto_detach_kernel_driver =
		reinterpret_cast<PTR_libusb_set_auto_detach_kernel_driver>(
			DYN_SYM(_dllHandle, "libusb_set_auto_detach_kernel_driver"));

	if (error)
	{
		unloadLibrary();
		return false;
	}

	return true;
}

void DriverOtherAmbiglow::unloadLibrary()
{
	if (_dllHandle != nullptr)
	{
		DYN_CLOSE(_dllHandle);
		_dllHandle = nullptr;
	}
}

bool DriverOtherAmbiglow::init(QJsonObject deviceConfig)
{
	if (!LedDevice::init(deviceConfig))
	{
		return false;
	}

	_vendorId = deviceConfig["vendorId"].toInt(DEFAULT_VENDOR_ID);
	_productId = deviceConfig["productId"].toInt(DEFAULT_PRODUCT_ID);
	_interface = deviceConfig["interface"].toInt(DEFAULT_INTERFACE);
	_address = static_cast<uint32_t>(deviceConfig["address"].toInt(static_cast<int>(DEFAULT_ADDRESS)));

	_frame.resize(_ledRGBCount);

	Debug(_log, "USB device    : {:04x}:{:04x}, interface {:d}", _vendorId, _productId, _interface);
	Debug(_log, "Buffer address: 0x{:04X}", _address);
	Debug(_log, "LED count     : {:d} ({:d} bytes)", _ledCount, _ledRGBCount);
	Info(_log, "Set the monitor's OSD Ambiglow mode to 'Static Mode', otherwise its own effect engine overwrites these colors");

	return true;
}

int DriverOtherAmbiglow::open()
{
	_isDeviceReady = false;

	if (!loadLibrary())
	{
		this->setInError("Unable to load libusb");
		return -1;
	}

	int rc = _fun_libusb_init(&_usbContext);
	if (rc != 0)
	{
		this->setInError(QString("libusb_init failed: %1").arg(_fun_libusb_error_name(rc)));
		return -1;
	}

	_deviceHandle = _fun_libusb_open_device_with_vid_pid(_usbContext,
							static_cast<uint16_t>(_vendorId), static_cast<uint16_t>(_productId));

	if (_deviceHandle == nullptr)
	{
		this->setInError(QString("Could not open USB device %1:%2. Is the monitor's USB upstream cable connected to this machine? DisplayPort alone is not enough.")
			.arg(_vendorId, 4, 16, QChar('0')).arg(_productId, 4, 16, QChar('0')));
		_fun_libusb_exit(_usbContext);
		_usbContext = nullptr;
		return -1;
	}

	if (_fun_libusb_set_auto_detach_kernel_driver != nullptr)
	{
		_fun_libusb_set_auto_detach_kernel_driver(_deviceHandle, 1);
	}

	rc = _fun_libusb_claim_interface(_deviceHandle, _interface);
	if (rc != 0)
	{
		this->setInError(QString("Could not claim interface %1: %2. Check permissions (udev rule) or another program using the device.")
			.arg(_interface).arg(_fun_libusb_error_name(rc)));
		_fun_libusb_close(_deviceHandle);
		_deviceHandle = nullptr;
		_fun_libusb_exit(_usbContext);
		_usbContext = nullptr;
		return -1;
	}

	Info(_log, "Opened Ambiglow device {:04x}:{:04x}", _vendorId, _productId);

	_isDeviceReady = true;
	return 0;
}

int DriverOtherAmbiglow::close()
{
	_isDeviceReady = false;

	if (_deviceHandle != nullptr)
	{
		_fun_libusb_release_interface(_deviceHandle, _interface);
		_fun_libusb_close(_deviceHandle);
		_deviceHandle = nullptr;
	}

	if (_usbContext != nullptr)
	{
		_fun_libusb_exit(_usbContext);
		_usbContext = nullptr;
	}

	return 0;
}

int DriverOtherAmbiglow::writeFiniteColors(const std::vector<ColorRgb>& ledValues)
{
	if (!_isDeviceReady || _deviceHandle == nullptr)
	{
		return -1;
	}

	const size_t wanted = ledValues.size() * sizeof(ColorRgb);
	if (_frame.size() != wanted)
	{
		_frame.resize(wanted);
	}
	std::memcpy(_frame.data(), ledValues.data(), wanted);

	const int written = _fun_libusb_control_transfer(_deviceHandle,
						REQ_TYPE_WRITE, REQ_WRITE,
						static_cast<uint16_t>((_address >> 16) & 0xFFFF),
						static_cast<uint16_t>(_address & 0xFFFF),
						_frame.data(),
						static_cast<uint16_t>(_frame.size()),
						TIMEOUT_MS);

	if (written < 0)
	{
		this->setInError(QString("Control transfer failed: %1").arg(_fun_libusb_error_name(written)));
		return -1;
	}

	return 0;
}

bool DriverOtherAmbiglow::isRegistered =
	hyperhdr::leds::REGISTER_LED_DEVICE("ambiglow", "leds_group_3_serial", DriverOtherAmbiglow::construct);
