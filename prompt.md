here is a concept of design for new operator data screen UI for customer household waste collection, please copy this, but not the content, i want ui but take whats useful from the ui. If it looks better. I want all functions working. make sure page color matches other parts of the app, dont copy header colors frm the screnshot.
2. I need a toggle button driver app header to toggle "household" and "bin collection" the rest of the app needs to adapt this change carefully in all places, please plan carefully and redirect pages correctly. Wehn household is selected it needs to household points need to show, only it need to be shown. hide bin colelction.

This is a substantial two-part feature. Let me investigate the current state of both before planning — the operator data screen internals, and how collection-type filtering could thread through the driver app.

Agent:Map operator data screen internals
IN
In the Flutter app /Users/zigma-mac/Documents/IWMS/iwms-government-app, I need a complete map of the "operator data screen" — the household waste-collection weighment form opened when a driver/operator collects a household (via QR scan or tapping a household tile). File: lib/modules/module2_driver/presentation/screens/operator_data_screen.dart (there may also be one under module3_operator).

Report with exact file:line references:

1. The full widget structure of operator_data_screen.dart: what fields/inputs it shows (weight entry, waste type selection, image capture, description, etc.), the state variables, and how the form is laid out.

2. Every FUNCTION the screen performs that must keep working if I redesign the UI: image capture (which package/method), weight entry, waste-type selection, the submit/finalize flow (what API endpoint it POSTs to, what payload/multipart fields — quote them), assignment_id handling, any per-waste-type sub-entries. Quote the submit method fully.

3. How it's opened and with what constructor arguments (search for `OperatorDataScreen(` / `operator_data_screen` usages). What data is passed in (customer, assignmentId, etc.)?

4. Does it currently support MULTIPLE waste items in one session (wet/dry/mixed as separate weighed entries with separate photos), or just one? How are wet/dry/mixed handled today?

5. The app's shared color/theme tokens used by the driver + operator screens — where are they (CaptainTheme, OperatorTheme)? List the key colors (background, surface, accent, success, warning, danger, text colors) so a redesign can match the existing app rather than the screenshot's header colors.

6. Any existing "waste item" / weighment model classes and how the captured data is structured before submit.

Report concisely but completely — I'm going to redesign this screen's UI (card-per-waste-item layout) while keeping all functions working, so I need to know exactly what to preserve. Do NOT modify anything.
Bash Find theme and waste model files
IN
find /Users/zigma-mac/Documents/IWMS/iwms-government-app/lib -iname "*theme*" -o -iname "*color*"; echo "---WASTE MODELS---"; find /Users/zigma-mac/Documents/IWMS/iwms-government-app/lib -iname "*waste*" -o -iname "*weigh*"

OUT
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/core/theme
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/logic/theme
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/core/theme/app_theme.dart
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/core/theme/app_colors.dart
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/logic/theme/theme_cubit.dart
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/modules/module2_driver/presentation/theme
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/modules/module5_supervisor/presentation/theme
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/modules/module1_citizen/citizen/theme
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/modules/module3_operator/presentation/theme
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/modules/module2_driver/presentation/theme/captain_theme.dart
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/modules/module2_driver/presentation/theme/driver_theme.dart
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/modules/module5_supervisor/presentation/theme/supervisor_theme.dart
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/modules/module1_citizen/citizen/theme/citizen_theme.dart
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/modules/module3_operator/presentation/theme/operator_theme.dart
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/modules/module1_citizen/citizen/dashboard/common/theme_tokens.dart
---WASTE MODELS---
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/modules/module1_citizen/citizen/track_waste.dart
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/modules/module5_supervisor/presentation/widgets/supervisor_waste_chart.dart
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/modules/module3_operator/presentation/screens/operator_weighbridge_screen.dart.dart
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/modules/module1_citizen/citizen/dashboard/track/models/waste_period.dart
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/modules/module1_citizen/citizen/dashboard/track/models/waste_summary.dart
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/modules/module1_citizen/citizen/dashboard/track/models/waste_reports.dart
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/modules/module1_citizen/citizen/dashboard/track/widgets/waste_stat_card.dart
Read operator_data_screen.dart
Read pending_record.dart
Agent:Map collection-type filtering points
IN
In the Flutter app /Users/zigma-mac/Documents/IWMS/iwms-government-app driver module (lib/modules/module2_driver/), I'm planning to add a header TOGGLE that switches the whole driver experience between "Household" and "Bin collection" modes — when Household is selected, only household trips/stops show and bin collection is hidden, and vice versa.

I need to know every place that currently distinguishes or lists the two collection types, so I can thread a single "selected collection mode" filter through correctly. Report with exact file:line references:

1. The driver header widget (driver_header.dart) — its current layout and where a toggle control could be added. Quote the top row structure.

2. driver_home_page.dart: how `_todayTrips` is loaded and used. The trips carousel (in captain_home_tab.dart) shows all trips — where would filtering by collection type happen? How does `OperatorTripToday.isHousehold` / `collectionType` work (already exists per earlier work)?

3. The Home tab (captain_home_tab.dart): how it renders bin trips (CollectionProgressMeter + _StopsTimeline) vs household trips (_HouseholdTimeline). Quote the branching.

4. The Map tab: how `_mapTrip`, `_customers`, `_tripStops` are chosen (I previously added `_openMapForTrip` and `_buildMapStopsForTrip`). Where does bin-vs-household get decided for the map?

5. The Scan FAB flow (`_openScanner`): it offers "Bin collection" vs "Household collection" choices — quote it. Would a global mode make one of these the default/only option?

6. Any place that counts/shows both trip types together (KPIs, "Trips today (2)", progress). List them.

7. Is there existing persistence (SharedPreferences) for a user toggle I can follow as a pattern (e.g. MapStylePrefs, CaptainThemeStore)? Quote how they persist a simple value.

Report concisely: the full inventory of collection-type-aware code paths in the driver module that a global Household/Bin toggle would need to touch, with file:line refs, plus the recommended single source of truth for the selected mode. Do NOT modify anything.
Read collection_history.dart
Bash Check ApiConfig endpoints and action sheet signature
IN
grep -n "desktopBase\|assignmentCustomerStatuses\|assignments\b\|customerList\|legacyRoleAssignEnabled" /Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/core/api_config.dart | head -30; echo "===ACTION SHEET SIG==="; sed -n '1,60p' /Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/modules/module2_driver/presentation/widgets/household_action_sheet.dart | grep -n "customerId\|customerName\|contactNo\|latitude\|longitude\|assignmentId\|Future\|required" 

OUT
26:  static const String desktopBase = kDesktopBase;
29:  static const String attendanceBase = '${desktopBase}attendance/';
30:  static const bool legacyRoleAssignEnabled = false;
33:      '${desktopBase}waste/citizen-summary/';
38:      '${desktopBase}waste/mark-household-status/';
39:  static const String customerList =
40:      '${desktopBase}customer-masters/customercreations/';
42:      '${desktopBase}customer-masters/customercreations/register-fcm-token/';
49:      '${desktopBase}citizen/complaint-tickets/';
51:      '${desktopBase}citizen/complaint-tickets/meta/';
56:      '${desktopBase}complaint-ticket/tickets/';
58:  static const String assignments =
59:      '${desktopBase}schedule-masters/daily-trip-assignments/';
61:      '${desktopBase}schedule-masters/daily-trip-assignments/';
63:      '${desktopBase}schedule-masters/bin-collection-events/';
64:  static const String assignmentCustomerStatuses =
65:      '${desktopBase}schedule-masters/daily-trip-household-collections/';
67:      '${desktopBase}schedule-masters/daily-trip-household-collections/';
69:      '${desktopBase}schedule-masters/daily-trip-assignments/';
70:  static const String tripShifts = '${desktopBase}schedule-masters/trip-plans/';
72:      '${desktopBase}schedule-masters/daily-trip-collection-points/';
74:      '${desktopBase}schedule-masters/trip-plans/';
76:      '${desktopBase}schedule-masters/trip-plan-collection-points/';
78:      '${desktopBase}schedule-masters/daily-trip-collection-points/tracking/';
80:      '${desktopBase}schedule-masters/daily-trip-collection-points/';
82:      '${desktopBase}schedule-masters/daily-trip-collection-points/optimize-route/';
84:      '${desktopBase}schedule-masters/daily-trip-assignments/generate-daily/';
86:      '${desktopBase}schedule-masters/daily-trip-collection-points/tracking/';
88:      '${desktopBase}schedule-masters/staff-templates/';
90:      '${desktopBase}transport-masters/vehicle-creation/';
===ACTION SHEET SIG===
17:Future<bool> showHouseholdActionSheet(
19:  required String customerId,
20:  required String customerName,
21:  required String contactNo,
22:  required String latitude,
23:  required String longitude,
24:  required String assignmentId,
45:          Text('ID: $customerId',
48:          Text(customerName,
53:          if (contactNo.isNotEmpty)
54:            Text('Contact: $contactNo',
Bash Search collection type references
IN
grep -rn "isHousehold\|collectionType\|Household\|household\|bin collection\|Bin collection\|BinCollection" /Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/modules/module2_driver --include=*.dart | head -100

OUT
(eval):1: no matches found: --include=*.dart
Both investigations are running in parallel. While they map the current code, let me note the plan shape so we're aligned — I'll flesh it out with exact file references once the agents report.

Part 1 — Redesign the household collection form (the screenshot's card-per-waste-item layout): a top context strip (date/time/vehicle/location), an "Add Waste Item" flow where each item is a card with weight (+quick-chips), image capture, and optional description, plus a totals footer and "Save All Entries" — but using the app's own theme tokens (not the screenshot's green/blue header), and preserving every existing function (image upload, weight, waste-type, the finalize API + assignment_id).

Part 2 — Header Household/Bin toggle: a single persisted "collection mode" as the source of truth, filtering the carousel, Home list, Map, and Scan FAB so only the selected type shows everywhere.

I'll wait for the two maps before writing any code, so the filtering threads through correctly and I keep all functions intact.

Read driver_header.dart
I now have a complete picture. Here is the map.

Operator Data Screen — Complete Map
There are two near-identical copies of this screen. They share ~95% of code (state, all functions, API calls, widget builders). The differences are only: theme tokens (CaptainTheme vs OperatorTheme), the AppBar/success-sheet navigation, and one finalize field. Your target for the redesign is the driver copy.

Driver (target): /Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/modules/module2_driver/presentation/screens/operator_data_screen.dart (2064 lines, uses CaptainTheme)
Operator: /Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/modules/module3_operator/presentation/screens/operator_data_screen.dart (2044 lines, uses OperatorTheme, uses go_router)
All line references below are the driver copy unless noted.

1. Widget structure, fields, state
Constructor / widget fields (driver :37-59, operator :39-61):


final String customerId, customerName, contactNo, latitude, longitude;
final bool skipBluetoothInit;   // default false
final String? assignmentId;
State variables (:63-86):

ImagePicker _picker — image capture
String screenUniqueId — generated per session via UniqueIdService.generateScreenUniqueId() (:124), regenerated on reset (:607)
bool connected, String latestWeight = "--", bool _isSubmitting, BluetoothConnection? _connection, bool _btConnecting, String? _connectedDeviceName
bool get _bluetoothSupported => Platform.isAndroid (:74) — scale UI is Android-only; iOS is manual-entry only
String? activeType — currently selected waste type (receives live scale weight)
OfflineSyncService _syncService, PendingRecordDao _pendingDao, PendingFinalizeDao _finalizeDao, CollectionHistoryService _historyService
bool _collectionSubmitted — return value passed back on pop
Map<String, TextEditingController> _manualWeightControllers — one per waste type
List<Map<String,dynamic>> wasteTypes — the type list (id + waste_type_name)
Map<String, Map<String,dynamic>> _wasteData — the core data model (see §6), keyed by lowercased type name
Layout (build at driver :1700, operator :1675):

WillPopScope → returns _collectionSubmitted on back
Scaffold (bg CaptainTheme.background) with gradient AppBar titled "Household Collection"
Body = SingleChildScrollView padding (16,16,16,120) with a Column:
_buildCollectionHeader(...) (:997) — gradient card: Live Weight big number, addedCount/total added chip, Bluetooth bar, Customer + Total metric tiles
_buildCustomerInfo() (:1247) — customer name/ID/contact card
Section title "Waste entries" + subtitle
Either "No waste types configured" empty state OR one _buildWasteSection(type, name) per waste type (:1782-1794), each wrapped in a KeyedSubtree
bottomNavigationBar (driver :1801) — "Total waste {kg}" + Submit button (calls _submitForm, disabled while _isSubmitting)
Per-waste-type card _buildWasteSection (:1369) contains, in order:

Header row: waste icon + displayName + "Photo required/captured" subtitle + status chip (Added/Pending)
Image area: either Image.file preview (tap → _showPreview) or a "Capture waste photo" placeholder
Weight display row + a manual weight TextField (:1549) — numeric, regex ^\d*\.?\d{0,2}$, onChanged → _updateManualWeight
Action row: Capture/Retake button (camera) + Add/Update/Save button (_handleAdd)
2. Functions that MUST keep working
Image capture — image_picker package. In the Capture button onPressed (:1600-1629):


final picked = await _picker.pickImage(source: ImageSource.camera);
if (picked == null) return;
final original = File(picked.path);
final compressed = await ImageCompressService.compress(original);
// stores compressed File into _wasteData[type]['image'], applies latestWeight, sets activeType
Compression: ImageCompressService.compress (image_compress_service.dart) uses flutter_image_compress (quality 60, 800x600, JPEG, to temp dir).

Weight entry — two paths:

Live: Bluetooth scale stream → latestWeight, and if activeType set + _canApplyLiveWeight, written into that type's weight (_connectToDevice stream, :2019-2047).
Manual: _updateManualWeight(type, raw) (:269) sets weight/finalWeight, also updates latestWeight.
Waste-type selection — types come from _fetchWasteTypes() (:164) GET ${desktopBase}waste/get-waste-types/, falling back to defaults [{id:1,Wet},{id:2,Dry},{id:3,Mixed}] if empty/failing. _applyWasteTypes (:401) builds _wasteData + controllers. Driver copy additionally calls _prioritizeWasteTypes (:382) ordering Wet→Dry→others (operator copy does NOT — that's a difference).

Per-type add/update (insert-waste-sub / update-waste-sub) — _handleAdd(type) (:459). This is the per-waste-type sub-entry. Quoted:


Future<void> _handleAdd(String type) async {
    final data = _wasteData[type]!;
    final image = data['image'] as File?;
    final wasteTypeId = data['waste_type_id']?.toString() ?? '';
    if (image == null) { AppFlash.warning(context, 'Capture image for $type first'); return; }
    if (wasteTypeId.isEmpty || wasteTypeId == 'null') { AppFlash.warning(context, 'Missing waste type for $type'); return; }
    final weightValue = data['weight']?.toString() ?? '--';
    if (weightValue.isEmpty || weightValue == "--") { AppFlash.warning(context, 'Please ensure weight is recorded for $type'); return; }
    final weight = weightValue;
    final isUpdate = data['isAdded'] == true;
    final uniqueId = data['unique_id']?.toString();
    _safeSetState(() => _isSubmitting = true);
    try {
      final uri = Uri.parse(isUpdate
            ? '${ApiConfig.desktopBase}waste/update-waste-sub/'
            : '${ApiConfig.desktopBase}waste/insert-waste-sub/');
      final request = http.MultipartRequest('POST', uri)
        ..headers.addAll(await _authHeaders())
        ..fields['screen_unique_id'] = screenUniqueId
        ..fields['customer_id'] = widget.customerId
        ..fields['waste_type'] = wasteTypeId
        ..fields['waste_type_id'] = wasteTypeId
        ..fields['weight'] = weight
        ..fields['latitude'] = widget.latitude
        ..fields['longitude'] = widget.longitude;
      if (isUpdate && uniqueId != null) { request.fields['unique_id'] = uniqueId; }
      request.files.add(await http.MultipartFile.fromPath('image', image.path));
      final streamed = await request.send();
      if (streamed.statusCode >= 400) { throw Exception("Server error ${streamed.statusCode}"); }
      final response = await http.Response.fromStream(streamed);
      dynamic result;
      try { result = json.decode(response.body); } catch (_) { throw Exception("Invalid JSON from backend"); }
      if (result['status'] != 'success') { throw Exception(result['message'] ?? "Unknown server error"); }
      final backendUnique = result['unique_id']?.toString();
      _safeSetState(() {
        final updated = Map<String, dynamic>.from(data);
        updated['isAdded'] = true;
        updated['finalWeight'] = weight;
        if (backendUnique != null) { updated['unique_id'] = backendUnique; }
        _wasteData[type] = updated;
        if (activeType == type) { activeType = null; }
      });
      await _fetchWasteRecord(type);
      if (!mounted) return;
      AppFlash.success(context, isUpdate ? "$type updated successfully" : "$type added successfully");
      return;
    } catch (err) {
      // OFFLINE fallback: build PendingRecord, upsert via _pendingDao (findByTypeAndScreen/update/insert),
      // reload offline, AppFlash.info "$type saved offline — will sync automatically"
      ...
    } finally { _safeSetState(() => _isSubmitting = false); }
  }
Multipart fields to preserve: screen_unique_id, customer_id, waste_type, waste_type_id, weight, latitude, longitude, optional unique_id (update only), and file field image. Response unique_id is captured. _fetchWasteRecord(type) (:423) POSTs waste/get-latest-waste/ to reconcile the backend weight/uid.

Submit / finalize — _submitForm() (driver :625). Quoted (driver version — note it POSTs assignment_id; the operator copy at :634-641 omits that field):


Future<void> _submitForm() async {
    _safeSetState(() => _isSubmitting = true);
    final totalWeight = _calculateTotalWeight();
    final summary = _buildSummarySnapshot();
    Future<void> syncLog(String status) async {
      if (!ApiConfig.legacyRoleAssignEnabled) return;   // currently FALSE → no-op
      if (widget.assignmentId == null || widget.assignmentId!.trim().isEmpty) return;
      try {
        final dio = await authorizedDio();
        await dio.post(ApiConfig.assignmentCustomerStatuses, data: {
            'assignment': widget.assignmentId,
            'customer': widget.customerId,
            'status': status == 'collection_completed' ? 'collected' : status,
            if (latitude.isNotEmpty) 'latitude': latitude,
            if (longitude.isNotEmpty) 'longitude': longitude,
          });
      } catch (_) {}
    }
    try {
      final uri = Uri.parse('${ApiConfig.desktopBase}waste/finalize-waste/');
      final request = http.MultipartRequest('POST', uri)
        ..headers.addAll(await _authHeaders())
        ..fields['screen_unique_id'] = screenUniqueId
        ..fields['customer_id'] = widget.customerId
        ..fields['entry_type'] = 'app'
        ..fields['assignment_id'] = widget.assignmentId ?? ''   // DRIVER ONLY
        ..fields['total_waste_collected'] = totalWeight.toString();
      final response = await request.send();
      final result = json.decode((await http.Response.fromStream(response)).body);
      if (result['status'] == 'success') {
        await _recordCollectionHistory(totalWeight);
        _collectionSubmitted = true;
        if (widget.assignmentId != null && widget.assignmentId!.trim().isNotEmpty) {
          await AssignmentStatusStore.setStatusForAssignment(widget.assignmentId!, widget.customerId, 'collected');
          await syncLog('collection_completed');
          await _maybeCompleteAssignmentFromStore(widget.assignmentId!);
        }
        await _showSuccessSheet(totalWeight, summary);
        _resetUI();
        _fetchWasteTypes();
      } else { throw Exception(result['message']); }
    } catch (e) {
      // OFFLINE: insert PendingFinalizeRecord(screenId, customerId, totalWeight, entryType:"app"),
      // try _syncService.syncAll() if internet, record history, update AssignmentStatusStore,
      // _showSuccessSheet(..., offline:true), _resetUI(), _fetchWasteTypes()
      ...
    } finally { _safeSetState(() => _isSubmitting = false); }
  }
Finalize multipart fields to preserve: screen_unique_id, customer_id, entry_type='app', total_waste_collected (+ assignment_id in driver copy). The whole per-session tie is screen_unique_id — the backend joins the sub-entries to the finalize via that id, so it must be constant across all _handleAdd calls and the finalize.

assignment_id handling: passed through the widget; used in finalize field (driver), syncLog status POST to assignmentCustomerStatuses, AssignmentStatusStore.setStatusForAssignment, and _maybeCompleteAssignmentFromStore (:740) which may auto-complete the whole assignment. Note ApiConfig.legacyRoleAssignEnabled = false currently, so syncLog, _fetchAssignmentCustomerIds, _markAssignmentComplete are all no-ops today — but keep the calls wired.

Other functions to preserve: _calculateTotalWeight (:731), _buildSummarySnapshot (wet/dry/mixed totals, :862), _recordCollectionHistory (:826), _resetUI (:603), _showSuccessSheet (:880), and full Bluetooth stack (:1875-2062): _ensureBluetoothPermissions, _initBluetooth, _pickScaleDevice (name hints AEBT/HC-05/…), _promptDevicePicker, _connectToDevice (parses newline-delimited weight lines from conn.input), _resetBluetooth, _reconnectBluetoothWithRetry, lifecycle hooks (didPopNext, didChangeAppLifecycleState).

3. How it's opened + constructor args
Three call sites, all passing customerId, customerName, contactNo, latitude, longitude, assignmentId (+ optional skipBluetoothInit):

Driver household action sheet — household_action_sheet.dart:121-133: on 'collect' action, Navigator.push(MaterialPageRoute(builder: (_) => OperatorDataScreen(...))), returns true on finalize. Entry fn showHouseholdActionSheet(...) (:17-24) requires customerId, customerName, contactNo, latitude, longitude, assignmentId.
Operator QR scanner — operator_qr_scanner.dart:508-519: on 'collect' after scanning/tapping a household, same push with skipBluetoothInit: false.
Router (go_router) — app_router.dart:263-278, path AppRoutePaths.operatorData: reads from state.extra map (customerId, customerName, contactNo, latitude, longitude, skipBluetoothInit, assignmentId).
4. Multiple waste items? — one entry PER TYPE, not multiple per type
Today the session supports one weighed entry per waste type (Wet, Dry, Mixed — and any API-configured types), each with its own photo + own weight + own backend unique_id. So a single household session does capture Wet, Dry, and Mixed as three separate weighed+photographed sub-entries simultaneously (each its own card, each _handleAdd'd independently, all sharing one screen_unique_id, then one finalize).

What it does not support: multiple distinct entries of the same type (e.g., two separate "Dry" weighments) — the _wasteData map is keyed by the lowercased type name, so a second capture on the same card overwrites/updates the first (Add becomes Update).

Wet/dry/mixed handling specifics: _wasteData keys matched by substring — _wasteAccent/_wasteIcon/_buildSummarySnapshot (:862) all use key.contains('wet'), .contains('dry'), else treated as mixed. Success-sheet pills are hardcoded Wet/Dry/Mixed (:932-934). If your redesign is truly card-per-item with arbitrary multiplicity, this fixed-key-per-type model (Map<String, Map> keyed by type name) is the main structural constraint to change — but the backend contract (screen_unique_id + per-sub waste_type_id) already allows multiple subs, so a List of items would map cleanly to repeated insert-waste-sub calls.

5. Theme tokens (match these in the redesign)
Driver = CaptainTheme (module2_driver/presentation/theme/captain_theme.dart) — dual light/dark, fixed royal-blue brand. Tokens are getters resolving live off CaptainThemeStore.isDark. Key light-mode values:

background #FFFFFF (dark #000000)
surface #FFFFFF (dark #151917); surfaceMuted #EFF2F7 (dark #1E2421)
primary #101E3C (deep royal navy, headers); primaryAccent #070F22; primarySoft #1B2F5C
accent #4D7CFF (royal ultramarine, CTAs — same both modes); accentDeep #2743D6; accentSoft #E8EEFF (dark #101A33)
strongText #0B1220 (dark #F2F5F3); mutedText #515C6E (dark #A3AFA9); hairline #D4DAE4 (dark #2C3330)
success #0E9F6E; warning #B45309; danger #DC2626; info #2563EB (all brighten in dark)
gold #B97207 / goldSoft #FBF0DC
headerGradient = primary→primaryAccent; accentGradient = accent→accentDeep
cardRadius 20, chipRadius 13; softShadow = none in light, soft black in dark
Operator = OperatorTheme (module3_operator/presentation/theme/operator_theme.dart) — static consts, charcoal-on-light with green CTAs:

background #FAFAFA; surface #FFFFFF; surfaceMuted #F3F4F6
primary #1F2937 (slate-800); primaryAccent #111827; primarySoft #374151
accent #0F8A58 (attendance green); accentDeep #0D3B26; accentSoft #E7F6EE
strongText #0F172A; mutedText #6B7280; hairline #E5E7EB
success #059669; warning #F59E0B; danger #DC2626; info #2563EB
headerGradient primary→primaryAccent; accentGradient accent→accentDeep; cardRadius 20, chipRadius 12
The screen also uses shared AppTextStyles (core/theme/app_text_styles.dart: heading2, bodyMedium, labelLarge) and AppColors.primary (in the BT device picker). Per-waste in-card accents are hardcoded: Wet = Color(0xFF0EA5E9), Dry = theme warning, Mixed/other = theme accent (_wasteAccent, :1328).

6. The "waste item" data model
There is no dedicated waste-item class — captured data lives in an inline Map<String, Map<String,dynamic>> _wasteData, built by _applyWasteTypes (:401), keyed by lowercased type name. Each entry:


{
  'waste_type_id': item['id'],    // backend id
  'label':         item['waste_type_name'],
  'unique_id':     null,          // backend sub-entry id after insert
  'image':         null,          // File? (compressed photo)
  'weight':        '--',          // String, current/live weight
  'finalWeight':   null,          // String?, confirmed weight (null while editing)
  'isAdded':       false,         // bool, sub-entry persisted
}
Helper readers: _weightTextFor (:262), _weightFromEntry (:856), _canApplyLiveWeight (:88).

Related persisted models:

PendingRecord (module3_operator/offline/pending_record.dart:99) — offline queue for insert/update-waste-sub: id, screenId, customerId, customerName, contactNo, wasteTypeId, weight(String), latitude/longitude(double?), imagePath, isUpdate, uniqueId(non-null, auto uid_<ms>), createdAt. Has toMap/fromMap/copyWith.
PendingFinalizeRecord (module3_operator/offline/pending_finalize_record.dart) — offline queue for finalize: screenId, customerId, totalWeight, entryType.
CollectionHistoryEntry / CollectionHistorySection (shared/models/collection_history.dart) — local history written by _recordCollectionHistory; section = {type, weight(String), imagePath}, entry = {customerId, customerName, collectedAt, sections[], totalWeight}.
API base: ApiConfig.desktopBase (core/api_config.dart:26). Endpoints used: waste/get-waste-types/, waste/get-latest-waste/, waste/insert-waste-sub/, waste/update-waste-sub/, waste/finalize-waste/; plus assignmentCustomerStatuses = schedule-masters/daily-trip-household-collections/ and assignments = schedule-masters/daily-trip-assignments/ (both gated by legacyRoleAssignEnabled=false, currently inert).

I did not modify any files.

Read driver_home_page.dart (lines 341-580)
Bash Find OperatorTripToday model
IN
grep -rn "class OperatorTripToday\|isHousehold\|collectionType\|householdCollections" /Users/zigma-mac/Documents/IWMS/iwms-government-app/lib --include="*.dart" | grep -iv "module2_driver/presentation/screens\|module2_driver/presentation/widgets" | head -40

OUT
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/modules/module5_supervisor/data/supervisor_models.dart:63:    required this.isHousehold,
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/modules/module5_supervisor/data/supervisor_models.dart:76:  final bool isHousehold;
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/modules/module5_supervisor/data/supervisor_models.dart:100:      isHousehold: false,
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/modules/module5_supervisor/data/supervisor_models.dart:120:      isHousehold: true,
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/modules/module5_supervisor/presentation/widgets/supervisor_assignment_detail_sheet.dart:452:                        stop.isHousehold
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/modules/module5_supervisor/presentation/widgets/supervisor_assignment_detail_sheet.dart:592:            stop.isHousehold
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/modules/module1_citizen/citizen/driver_details.dart:22:  final String collectionType = 'Wet Waste';
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/modules/module1_citizen/citizen/driver_details.dart:81:                  'Type: $collectionType',
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/data/models/operator_trip_models.dart:320:class OperatorTripToday {
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/data/models/operator_trip_models.dart:344:  final String? collectionType;
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/data/models/operator_trip_models.dart:346:  final List<OperatorTripHouseholdStop> householdCollections;
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/data/models/operator_trip_models.dart:355:    this.collectionType,
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/data/models/operator_trip_models.dart:356:    this.householdCollections = const [],
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/data/models/operator_trip_models.dart:382:        collectionType: collectionType,
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/data/models/operator_trip_models.dart:383:        householdCollections: householdCollections,
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/data/models/operator_trip_models.dart:403:  bool get isHousehold =>
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/data/models/operator_trip_models.dart:404:      collectionType == 'household_collection' ||
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/data/models/operator_trip_models.dart:405:      collectionType == 'bulk_waste_collection';
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/data/models/operator_trip_models.dart:456:      collectionType: json['collection_type']?.toString(),
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/data/models/operator_trip_models.dart:457:      householdCollections: (json['household_collections'] as List? ?? [])
Read captain_theme.dart (lines 2-51)
Read captain_home_tab.dart (lines 2-231)
Bash Find CaptainHomeTab usage and map tab
IN
grep -n "CaptainHomeTab\|_todayTrips\|onOpenMap\|_openMapForTrip\|_mapTrip\|_HomeTab\|_MapTab\|Trips today\|trips today\|_buildMapTab\|onScan" /Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/modules/module2_driver/presentation/screens/driver_home_page.dart

OUT
155:  OperatorTripToday? _mapTrip;
156:  List<OperatorTripToday> _todayTrips = [];
444:        _mapTrip = mapTrip;
445:        _todayTrips = todayTrips;
555:  void _openMapForTrip(OperatorTripToday trip) {
558:      _mapTrip = trip;
698:        return CaptainHomeTab(
699:          trips: _todayTrips,
703:          onOpenMap: _openMapForTrip,
704:          onScan: _openScanner,
709:        return _HomeTab(
721:              (_mapTrip?.isHousehold ?? false) ? null : _mapTrip?.routeGeojson,
722:          activeTripId: _mapTrip?.assignmentUniqueId ?? _activeTripId,
951:class _HomeTab extends StatefulWidget {
952:  const _HomeTab({
993:  State<_HomeTab> createState() => _HomeTabState();
996:class _HomeTabState extends State<_HomeTab> with TickerProviderStateMixin {
1109:  void didUpdateWidget(covariant _HomeTab oldWidget) {
Read captain_home_tab.dart (lines 441-520)
Bash Find MapStylePrefs class
IN
grep -rn "class MapStylePrefs\|_prefsKey\|setString\|getString" /Users/zigma-mac/Documents/IWMS/iwms-government-app/lib --include="*.dart" | grep -i "mapstyle\|MapStyle" ; grep -rln "class MapStylePrefs" /Users/zigma-mac/Documents/IWMS/iwms-government-app/lib --include="*.dart"

OUT
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/core/map/map_style.dart:13:class MapStylePrefs {
/Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/core/map/map_style.dart
Read map_style.dart (lines 2-56)
I have a complete picture. Here is the inventory.

Household/Bin toggle — driver module inventory
The collection-type distinction is driven entirely by one model getter: OperatorTripToday.isHousehold (returns true for collectionType == 'household_collection' || 'bulk_waste_collection') at /Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/data/models/operator_trip_models.dart:403-405. Field collectionType is at :344, parsed from JSON collection_type at :456. There is no filtering by type anywhere today — all trips for the day are carried together in _todayTrips and shown in a carousel.

1. Driver header — where a toggle goes
File: .../presentation/widgets/driver_header.dart. The top row is the entire header content (build, lines 128-161):


child: Row(
  children: [
    _buildAvatarButton(compact: widget.collapsed),
    const SizedBox(width: 11),
    Expanded(child: _buildIdentity(compact: widget.collapsed)),
    const SizedBox(width: 8),
    _logoutButton(compact: widget.collapsed),
  ],
),
A segmented Household/Bin toggle would slot as a new row below this Row (inside the AnimatedPadding child, converting it to a Column), or replace the _buildIdentity center. The widget already has a collapsed bool pattern (:44-45, :146-148) showing how it accepts external state; the toggle would come in as a new constructor param + callback since DriverHeader is a StatefulWidget that doesn't own trip data. It's constructed in driver_home_page.dart (search DriverHeader( in _buildShell) where _todayTrips/mode state lives.

2. _todayTrips load & use, and where filtering would happen
File: .../presentation/screens/driver_home_page.dart.

State fields: _todayTrips at :156, _todayTrip (primary bin trip) :151, _mapTrip :155.
Loaded in _loadAssignmentsForDriver via _tripRepository.fetchMyTripsToday() at :375. Primary trip = first with collection points, else first (:381-388). Committed to state at :439-459 (_todayTrips = todayTrips :445).
Passed into the Home tab unfiltered at :699: CaptainHomeTab(trips: _todayTrips, ...).
The carousel (captain_home_tab.dart) renders ALL of widget.trips — see _buildTripCarousel loop .../captain_home_tab.dart:256-266 and the multi = trips.length > 1 branch at :152, :167-176.
Recommended filter point: apply the selected mode when passing trips: at driver_home_page.dart:699 (e.g. _todayTrips.where((t) => t.isHousehold == householdMode)), and derive _mapTrip from the filtered list. This is the single choke point that feeds the carousel, hero card, and section timelines.

3. Home tab bin-vs-household branching
File: .../presentation/screens/captain_home_tab.dart:191-207 (_buildBody):


if (t.isHousehold) ...[
  _SectionTitle(title: 'Households',
    trailing: '${t.progress.collected}/${t.progress.total} done'),
  const SizedBox(height: 10),
  _HouseholdTimeline(trip: t, onChanged: widget.onRefresh),
] else ...[
  CollectionProgressMeter(collectionPoints: t.collectionPoints),
  const SizedBox(height: 16),
  _SectionTitle(title: 'Collection points',
    trailing: '${t.progress.collected}/${t.progress.total} done'),
  const SizedBox(height: 10),
  _StopsTimeline(trip: t, onChanged: widget.onRefresh),
],
_HouseholdTimeline is defined at :1170 (reads trip.householdCollections, :1178); _HouseholdTile at :1219; _StopsTimeline/CollectionProgressMeter are the bin path. This branch is per selected trip t, so once the carousel is filtered to one mode it stays correct automatically.

4. Map tab — how _mapTrip, _customers, _tripStops are chosen
File: .../presentation/screens/driver_home_page.dart.

_buildMapStopsForTrip(trip) at :479-551 is the bin-vs-household decision for the map: if (trip.isHousehold) (:487) builds customer pins from trip.householdCollections (:488-512); else builds numbered bin _TripPlannedStops from detail.collectionPoints (:515-546).
Default map trip set in load at :436-437 (mapTrip = todayTrip), stored :444.
_openMapForTrip(trip) at :555-564 rebuilds _customers/_tripStops for a tapped carousel card and switches to the Map tab. Wired as onOpenMap: _openMapForTrip at :703 and invoked from carousel/hero cards (captain_home_tab.dart:175, :261).
Map tab render passes route conditionally on household at :720-722: activeRouteGeojson: (_mapTrip?.isHousehold ?? false) ? null : _mapTrip?.routeGeojson.
With a global mode, _mapTrip should default to the first trip of the selected mode (adjust :436), and the toggle flip should call something like _openMapForTrip on the new mode's trip.

5. Scan FAB flow
File: .../presentation/screens/driver_home_page.dart, _openScanner at :793-855. It shows a bottom sheet titled "What are you collecting?" (:812) with two _ScanChoiceTiles:


_ScanChoiceTile(icon: Icons.delete_rounded, color: CaptainTheme.accent,
  title: 'Bin collection', subtitle: 'Scan a bin QR and record its weight',
  onTap: () => Navigator.of(sheetContext).pop('bin')),               // :820-826
_ScanChoiceTile(icon: Icons.home_work_rounded, color: CaptainTheme.info,
  title: 'Household collection',
  subtitle: 'Scan a customer QR, enter wet / dry / mixed weights',
  onTap: () => Navigator.of(sheetContext).pop('household')),          // :828-834
Dispatch: choice == 'bin' → OperatorTripScanScreen (:842-847); choice == 'household' → OperatorQRScanner (:848-853). With a global mode you can skip the sheet and jump straight to the matching scanner (bin mode → OperatorTripScanScreen, household mode → OperatorQRScanner), making the mode the default/only path.

6. Places counting/showing both types together
The Home carousel itself — mixes bin + household trips in one swipeable list: captain_home_tab.dart:37-38 (doc), :152 (multi), :167-176, :256-266, dots _CarouselDots :272/:318.
Per-trip KPIs are per selected trip (not cross-type sums): progress trailing: '${t.progress.collected}/${t.progress.total} done' at :194 and :203; hero-card ring uses trip.progress at :483. No aggregate "Trips today (2)" counter was found — the count surfaces only implicitly via _CarouselDots(count: trips.length).
Collection-type visual identity (would follow the mode): _CollectionTypePill :350-400 (label map at :397-400), _TripHeroCard._typeTint :459-469.
Map load builds stops only for the single _mapTrip, so no cross-type mixing there.
Net: the only real "both together" surface is the carousel (dots + card list). Filtering _todayTrips at the CaptainHomeTab(trips:) call collapses it to one mode.

7. Existing persistence patterns to follow
Two clean patterns, both in this module's orbit:

CaptainThemeStore — .../presentation/theme/captain_theme.dart:8-34. Static class + ValueNotifier<bool> isDark (:12), load() reads prefs.getBool('captain_dark_mode') (:14-23), setDark() writes it (:25-31), toggle() (:33). The shell rebuilds via ValueListenableBuilder<bool>(valueListenable: CaptainThemeStore.isDark, ...) at driver_home_page.dart:239-249 and :3587. This is the ideal template: a bool/enum notifier the whole shell listens to.

MapStylePrefs — /Users/zigma-mac/Documents/IWMS/iwms-government-app/lib/core/map/map_style.dart:13-37. Enum-based:


static const _key = 'map_style';
static Future<MapStyle> load() async {
  final prefs = await SharedPreferences.getInstance();
  final name = prefs.getString(_key);
  return MapStyle.values.firstWhere((s) => s.name == name, orElse: () => kDefaultMapStyle);
}
static Future<void> save(MapStyle style) async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.setString(_key, style.name);
}
Recommended single source of truth
Create a CollectionMode { household, bin } enum with a CaptainThemeStore-style static store (e.g. CollectionModeStore with ValueNotifier<CollectionMode> mode, load()/set() persisting a string via SharedPreferences, mirroring both patterns above). Then:

driver_home_page.dart wraps _buildShell (or the tab body) in a ValueListenableBuilder<CollectionMode> alongside the existing theme listener at :239.
Filter at the two feed points: CaptainHomeTab(trips: ...) at :699 and the _mapTrip/_buildMapStopsForTrip default at :436-437 / :555.
Make the header toggle (driver_header.dart Row :149-157) call CollectionModeStore.set(...).
Optionally short-circuit _openScanner (:793) to the mode's scanner.
All downstream branching (isHousehold at captain_home_tab.dart:191, driver_home_page.dart:487/721) then stays correct unchanged, because each trip already self-describes its type — the toggle only needs to control which trips reach those branches.

No files were modified.

I have the full operator-data-screen map. Waiting on the second agent (collection-type filtering inventory) before I finalize the plan — I don't want to design the toggle's ripple effects without that complete picture.

I now have a complete map of both the operator data screen (every function, API field, and the screen_unique_id session contract I must preserve) and the collection-type filtering points (the isHousehold getter is the one distinction; the carousel is the only place both types mix).

Before I build ~this much UI + wiring, three decisions genuinely change what I implement — locking them now avoids building the wrong thing:

AskUserQuestion
OUT
Your questions have been answered: "How should the redesigned household collection form be structured? (The screenshot shows an 'Add Waste Item' list; the app's backend today expects one weighed+photographed entry per configured waste type — Wet/Dry/Mixed — tied by a session id.)"="Restyle per-type cards (Recommended)", "The screenshot has an optional 'Description' field per item. The backend's waste sub-entry has no description field today. What do you want?"="Omit it (Recommended)", "With the new header Household/Bin toggle, what should the center Scan (QR) button do?"="Go straight to mode's scanner (Recommended)". You can now continue with these answers in mind.
All three locked in. This is a large build, so I'll do it in two parts and verify each. Starting with Part 2 (the toggle) — it's the more structural piece. Let me mirror the existing CaptainThemeStore pattern for a new CollectionModeStore.

Read captain_theme.dart (lines 2-35)
Write collection_mode_store.dart
46 lines
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Which kind of collection the driver is working right now.
enum CollectionMode { household, bin }

/// The driver's selected collection mode — Household or Bin — persisted across
/// launches and toggled from the header. The Captain shell listens to [mode]
/// and rebuilds, so the carousel, home list, map and scan button all show only
/// the selected mode's trips.
///
/// Mirrors [CaptainThemeStore]'s notifier+SharedPreferences pattern so the shell
/// can listen with a `ValueListenableBuilder` exactly the same way.
class CollectionModeStore {
  CollectionModeStore._();

  static const String _prefsKey = 'driver_collection_mode';

  /// Default is bin collection (the app's original single-mode behaviour).
  static final ValueNotifier<CollectionMode> mode =
      ValueNotifier<CollectionMode>(CollectionMode.bin);

  static Future<void> load() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final name = prefs.getString(_prefsKey);
      mode.value = CollectionMode.values.firstWhere(
        (m) => m.name == name,
        orElse: () => CollectionMode.bin,
      );
    } catch (_) {
      // Keep the default if prefs are unavailable.
    }
  }

  static Future<void> set(CollectionMode value) async {
    mode.value = value;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_prefsKey, value.name);
    } catch (_) {}
  }

  static bool get isHousehold => mode.value == CollectionMode.household;
}
Now load it at startup alongside CaptainThemeStore.load(). Let me find where that's called.

Bash Find where CaptainThemeStore.load is called
IN
cd /Users/zigma-mac/Documents/IWMS/iwms-government-app
grep -rn "CaptainThemeStore.load()" lib/ | head

OUT
lib/modules/module2_driver/presentation/screens/driver_home_page.dart:170:    CaptainThemeStore.load();
sorry continue
Continuing. Let me wire CollectionModeStore.load() alongside the theme store.

Read driver_home_page.dart (lines 161-180)
Edit driver_home_page.dart
Added 2 lines
Bash List imports in driver_home_page.dart
IN
cd /Users/zigma-mac/Documents/IWMS/iwms-government-app
grep -n "^import" lib/modules/module2_driver/presentation/screens/driver_home_page.dart | head -30

OUT
1:import 'dart:math';
3:import 'package:dio/dio.dart';
4:import 'package:flutter/material.dart';
5:import 'package:flutter_bloc/flutter_bloc.dart';
6:import 'package:flutter_map/flutter_map.dart';
7:import 'package:animations/animations.dart';
8:import 'package:iwms_citizen_app/core/ui/app_copy.dart';
9:import 'package:iwms_citizen_app/core/ui/app_flash.dart';
10:import 'package:latlong2/latlong.dart';
12:import '../../../../core/di.dart';
13:import '../../../../core/geofence_config.dart';
14:import 'package:iwms_citizen_app/data/models/operator_trip_models.dart';
15:import 'package:iwms_citizen_app/data/models/vehicle_model.dart';
16:import 'package:iwms_citizen_app/data/repositories/operator_trip_repository.dart';
17:import '../../../../logic/vehicle_tracking/vehicle_bloc.dart';
18:import '../../../../logic/vehicle_tracking/vehicle_event.dart';
19:import 'package:iwms_citizen_app/logic/auth/auth_bloc.dart';
20:import 'package:iwms_citizen_app/logic/auth/auth_event.dart';
21:import 'package:iwms_citizen_app/logic/auth/auth_state.dart';
22:import 'package:iwms_citizen_app/core/api_config.dart';
23:import 'package:iwms_citizen_app/core/map/map_style.dart';
24:import 'package:iwms_citizen_app/core/ors_service.dart';
25:import 'package:iwms_citizen_app/core/network/authorized_dio.dart';
26:import 'package:iwms_citizen_app/modules/module2_driver/presentation/screens/attendance/attendance_driver.dart';
27:import 'package:iwms_citizen_app/modules/module2_driver/presentation/screens/captain_home_tab.dart';
28:import 'package:iwms_citizen_app/modules/module2_driver/presentation/theme/captain_theme.dart';
29:import 'package:iwms_citizen_app/modules/module2_driver/presentation/theme/driver_theme.dart';
30:import 'package:iwms_citizen_app/modules/module2_driver/presentation/widgets/captain_glass.dart';
31:import 'package:iwms_citizen_app/modules/module2_driver/presentation/widgets/captain_nav_bar.dart';
32:import 'package:iwms_citizen_app/modules/module2_driver/presentation/widgets/driver_header.dart';
Edit driver_home_page.dart
Added 1 line
Bash Find ValueListenableBuilder wrapping theme store
IN
cd /Users/zigma-mac/Documents/IWMS/iwms-government-app
grep -n "ValueListenableBuilder<bool>\|CaptainThemeStore.isDark" lib/modules/module2_driver/presentation/screens/driver_home_page.dart

OUT
242:            return ValueListenableBuilder<bool>(
243:              valueListenable: CaptainThemeStore.isDark,
2058:    final dark = CaptainThemeStore.isDark.value;
3589:              child: ValueListenableBuilder<bool>(
3590:                valueListenable: CaptainThemeStore.isDark,
Read driver_home_page.dart (lines 226-265)
Let me wrap this with a nested ValueListenableBuilder<CollectionMode>:

Edit driver_home_page.dart
Added 7 lines
Now update _buildShell's signature to accept the mode, and thread it into _buildTab/CaptainHomeTab.

Read driver_home_page.dart (lines 263-292)
Edit driver_home_page.dart
Added 3 lines
Expected — now let's find the _buildTab method to filter trips, and add the _onCollectionModeChanged handler. Let me view the rest of _buildShell and _buildTab.

Read driver_home_page.dart (lines 294-343)
Read driver_home_page.dart (lines 661-735)
You've hit your session limit · resets 2am (Asia/Calcutta)

