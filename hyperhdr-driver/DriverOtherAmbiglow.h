#pragma once

#ifndef PCH_ENABLED
	#include <cstdint>
	#include <vector>
#endif

#include <led-drivers/LedDevice.h>

// Minimal libusb surface, resolved at runtime so libusb is not a build dependency
// (same approach as ProviderSpiLibFtdi uses for libftdi).
#ifdef _WIN32
	#define AMBIGLOW_USB_CALL __cdecl
#else
	#define AMBIGLOW_USB_CALL
#endif

struct libusb_context;
struct libusb_device_handle;

typedef int   (AMBIGLOW_USB_CALL *PTR_libusb_init)(libusb_context** ctx);
typedef void  (AMBIGLOW_USB_CALL *PTR_libusb_exit)(libusb_context* ctx);
typedef libusb_device_handle* (AMBIGLOW_USB_CALL *PTR_libusb_open_device_with_vid_pid)(libusb_context* ctx, uint16_t vid, uint16_t pid);
typedef void  (AMBIGLOW_USB_CALL *PTR_libusb_close)(libusb_device_handle* handle);
typedef int   (AMBIGLOW_USB_CALL *PTR_libusb_set_auto_detach_kernel_driver)(libusb_device_handle* handle, int enable);
typedef int   (AMBIGLOW_USB_CALL *PTR_libusb_claim_interface)(libusb_device_handle* handle, int interface_number);
typedef int   (AMBIGLOW_USB_CALL *PTR_libusb_release_interface)(libusb_device_handle* handle, int interface_number);
typedef int   (AMBIGLOW_USB_CALL *PTR_libusb_control_transfer)(libusb_device_handle* handle, uint8_t requestType, uint8_t request,
											 uint16_t value, uint16_t index, unsigned char* data,
											 uint16_t length, unsigned int timeout);
typedef const char* (AMBIGLOW_USB_CALL *PTR_libusb_error_name)(int errcode);

///
/// Ambiglow LEDs built into Philips Evnia monitors.
///
/// The LEDs are driven by an ENE MCU inside the monitor, which appears on the monitor's
/// USB upstream as 0cf2:a201. Its interface 0 is vendor specific with no endpoints, so
/// registers are read and written with plain USB control transfers:
///
///   write: bmRequestType=0x40, bRequest=0x80, wValue=addr>>16, wIndex=addr&0xFFFF
///
/// Writing RGB triplets to the source colour buffer sets every LED; the monitor's own
/// effect engine renders that buffer. The monitor's OSD must have Ambiglow set to
/// "Static Mode" - in an animated mode the firmware generates its own frames and
/// discards whatever the host writes.
///
class DriverOtherAmbiglow : public LedDevice
{
public:
	explicit DriverOtherAmbiglow(const QJsonObject& deviceConfig);
	~DriverOtherAmbiglow() override;

	static LedDevice* construct(const QJsonObject& deviceConfig);

protected:
	bool init(QJsonObject deviceConfig) override;
	int open() override;
	int close() override;
	int writeFiniteColors(const std::vector<ColorRgb>& ledValues) override;

private:
	bool loadLibrary();
	void unloadLibrary();

	void*					_dllHandle;
	libusb_context*			_usbContext;
	libusb_device_handle*	_deviceHandle;

	int			_vendorId;
	int			_productId;
	int			_interface;
	uint32_t	_address;

	std::vector<uint8_t> _frame;

	PTR_libusb_init								_fun_libusb_init;
	PTR_libusb_exit								_fun_libusb_exit;
	PTR_libusb_open_device_with_vid_pid			_fun_libusb_open_device_with_vid_pid;
	PTR_libusb_close							_fun_libusb_close;
	PTR_libusb_set_auto_detach_kernel_driver	_fun_libusb_set_auto_detach_kernel_driver;
	PTR_libusb_claim_interface					_fun_libusb_claim_interface;
	PTR_libusb_release_interface				_fun_libusb_release_interface;
	PTR_libusb_control_transfer					_fun_libusb_control_transfer;
	PTR_libusb_error_name						_fun_libusb_error_name;

	static bool isRegistered;
};
