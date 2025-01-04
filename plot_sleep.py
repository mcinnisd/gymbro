from pymongo import MongoClient
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import pytz
import matplotlib.patches as mpatches  # Move mid-function import to the top

########################################################
# TIME PARSING & CONVERSION
########################################################

def parse_gmt_string(gmt_str):
    """
    E.g. "2025-01-02T03:49:00.0" => UTC datetime
    We'll strip the trailing ".0" if needed, then parse.
    """
    # A simpler approach to remove everything after a dot, if always ".0" or similar
    if "." in gmt_str:
        gmt_str = gmt_str.split(".")[0]
    dt_utc = datetime.strptime(gmt_str, "%Y-%m-%dT%H:%M:%S")
    return dt_utc.replace(tzinfo=pytz.utc)

def parse_gmt_millis(millis):
    """
    Convert Unix epoch ms to Python datetime (UTC).
    """
    return datetime.fromtimestamp(millis / 1000.0, tz=pytz.utc)

def convert_to_est(dt_utc):
    """
    Convert a UTC datetime to Eastern Time (America/New_York).
    """
    est = pytz.timezone("America/New_York")
    return dt_utc.astimezone(est)

########################################################
# STAGE MAPPING
########################################################

stage_colors = {0: 'navy', 1: 'green', 2: 'magenta', 3: 'red'}
stage_heights = {0: 1, 1: 2, 2: 3, 3: 4}
stage_labels = {0: "Deep", 1: "Core", 2: "REM", 3: "Awake"}

########################################################
# Optional Helper for Time-Value Data
########################################################

def extract_time_series(data_list, time_key, value_key, parse_time_func):
    """
    A small helper function to DRY up the repeated pattern of:
    - parse time from each entry
    - convert to EST
    - collect the 'value' or 'activityLevel'
    Returns two lists: (times, values).
    """
    times = []
    values = []
    for d in data_list:
        # Decide which parse function to use (parse_gmt_string vs parse_gmt_millis)
        dt_utc = parse_time_func(d[time_key])
        dt_est = convert_to_est(dt_utc)
        times.append(dt_est)
        values.append(d[value_key])
    return times, values

########################################################
# MAIN "OVERVIEW" PLOT
########################################################

def plot_sleep_overview(sleep_doc):
    """
    Similar to before, but for the final subplot (6), we'll create
    a merged list of non-overlapping segments that fill the entire min->max time
    with 'core'=1 by default, then overlay deep, rem, awake.
    """
    sleep_data = sleep_doc["sleep_data"]
    fig = plt.figure(figsize=(12, 8))

    # 1) Movement
    movement = sleep_data.get("sleepMovement", [])
    move_times, move_values = extract_time_series(
        movement, time_key="startGMT", value_key="activityLevel",
        parse_time_func=parse_gmt_string
    )
    ax1 = fig.add_subplot(3, 2, 1)
    ax1.plot(move_times, move_values, label="Movement")
    ax1.set_title("Sleep Movement (Activity Level)")
    ax1.set_xlabel("Time (EST)")
    ax1.set_ylabel("Activity Level")
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    plt.xticks(rotation=45)

    # 2) Heart Rate
    heartrate = sleep_data.get("sleepHeartRate", [])
    hr_times, hr_values = extract_time_series(
        heartrate, time_key="startGMT", value_key="value",
        parse_time_func=parse_gmt_millis
    )
    ax2 = fig.add_subplot(3, 2, 2)
    ax2.plot(hr_times, hr_values, color="red")
    ax2.set_title("Sleep Heart Rate")
    ax2.set_xlabel("Time (EST)")
    ax2.set_ylabel("BPM")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    plt.xticks(rotation=45)

    # 3) Sleep Stress
    sleep_stress = sleep_data.get("sleepStress", [])
    st_times, st_values = extract_time_series(
        sleep_stress, time_key="startGMT", value_key="value",
        parse_time_func=parse_gmt_millis
    )
    ax3 = fig.add_subplot(3, 2, 3)
    ax3.plot(st_times, st_values, color="orange")
    ax3.set_title("Sleep Stress")
    ax3.set_xlabel("Time (EST)")
    ax3.set_ylabel("Stress Value")
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    plt.xticks(rotation=45)

    # 4) Body Battery
    body_battery = sleep_data.get("sleepBodyBattery", [])
    bb_times, bb_values = extract_time_series(
        body_battery, time_key="startGMT", value_key="value",
        parse_time_func=parse_gmt_millis
    )
    ax4 = fig.add_subplot(3, 2, 4)
    ax4.plot(bb_times, bb_values, color="green")
    ax4.set_title("Sleep Body Battery")
    ax4.set_xlabel("Time (EST)")
    ax4.set_ylabel("Battery Value")
    ax4.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    plt.xticks(rotation=45)

    # 5) HRV
    hrv_data = sleep_data.get("hrvData", [])
    hrv_times, hrv_values = extract_time_series(
        hrv_data, time_key="startGMT", value_key="value",
        parse_time_func=parse_gmt_millis
    )
    ax5 = fig.add_subplot(3, 2, 5)
    ax5.plot(hrv_times, hrv_values, color="purple")
    ax5.set_title("Sleep HRV (ms)")
    ax5.set_xlabel("Time (EST)")
    ax5.set_ylabel("HRV (ms)")
    ax5.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    plt.xticks(rotation=45)

    # 6) Sleep Stages (No Overlap)
    ax_stages = fig.add_subplot(3, 2, 6)
    ax_stages.set_title("Sleep Stages (No Overlap, bars)")
    ax_stages.set_xlabel("Time (EST)")
    ax_stages.set_ylabel("Stage Height")
    ax_stages.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    plt.xticks(rotation=45)

    # Parse the raw levels
    raw_levels = sleep_data.get("sleepLevels", [])
    for lvl in raw_levels:
        start_utc = parse_gmt_string(lvl["startGMT"])
        end_utc   = parse_gmt_string(lvl["endGMT"])
        s_est = convert_to_est(start_utc)
        e_est = convert_to_est(end_utc)
        stg = lvl["activityLevel"]  # 0..3

        color = stage_colors.get(stg, 'gray')
        height = stage_heights.get(stg, 2)
        width_days = (e_est - s_est).total_seconds() / 86400
        ax_stages.bar(s_est, height, width=width_days, bottom=0, 
                      color=color, alpha=0.7, align='edge')

    # Build custom legend
    legend_patches = [
        mpatches.Patch(color=stage_colors[s], label=stage_labels[s]) 
        for s in stage_labels
    ]
    ax_stages.legend(handles=legend_patches, loc='upper right')

    fig.tight_layout()
    plt.show()

########################################################
# 2) OVERLAID PLOT: Sleep Bars + HR + HRV + Respiration
########################################################

def plot_overlaid_sleep_stages_lines(sleep_doc):
    """
    Single plot with:
    - Sleep stages as bars on one axis (0..something)
    - Overlaid lines for heart rate, HRV, respiration (etc).
    """
    sleep_data = sleep_doc["sleep_data"]

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.set_xlabel("Time (EST)")
    ax.set_ylabel("Sleep Stage (bars)")

    # 1) Plot the bars for stages
    sleep_levels = sleep_data.get("sleepLevels", [])
    for lvl in sleep_levels:
        start_utc = parse_gmt_string(lvl["startGMT"])
        end_utc   = parse_gmt_string(lvl["endGMT"])
        stage     = lvl["activityLevel"]
        start_est = convert_to_est(start_utc)
        end_est   = convert_to_est(end_utc)
        color     = stage_colors.get(stage, 'gray')
        height    = stage_heights.get(stage, 2)
        start_num = mdates.date2num(start_est)
        end_num   = mdates.date2num(end_est)
        width     = end_num - start_num
        ax.bar(start_num, height, width=width, bottom=0, 
               color=color, alpha=0.7, align='edge')

    # Legend for stage bars
    legend_patches = [
        plt.Rectangle((0, 0), 1, 1, color=stage_colors[s], label=stage_labels[s]) 
        for s in sorted(stage_colors.keys())
    ]
    ax.legend(handles=legend_patches, loc='upper left')

    # Format time axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    plt.xticks(rotation=45)

    # 2) Twin axis for HR, HRV, etc.
    ax2 = ax.twinx()
    ax2.set_ylabel("HR / HRV / Resp")

    # Heart Rate
    hr_data = sleep_data.get("sleepHeartRate", [])
    hr_times, hr_values = extract_time_series(
        hr_data, time_key="startGMT", value_key="value",
        parse_time_func=parse_gmt_millis
    )
    ax2.plot(hr_times, hr_values, color='red', label='HR (BPM)', linewidth=1.2)

    # If you want to enable HRV lines or respiration lines, uncomment:
    # hrv_data = sleep_data.get("hrvData", [])
    # hrv_times, hrv_values = extract_time_series(
    #     hrv_data, time_key="startGMT", value_key="value",
    #     parse_time_func=parse_gmt_millis
    # )
    # ax2.plot(hrv_times, hrv_values, color='purple', label='HRV (ms)', linewidth=1.2)

    # lines_legend = ax2.legend(loc='upper right')
    # Or combine legends if you prefer
    
		# -- HRV
	# hrv_data = sleep_data.get("hrvData", [])
	# hrv_x = []
	# hrv_y = []
	# for hrv in hrv_data:
	#     dt_utc = parse_gmt_millis(hrv["startGMT"])
	#     dt_est = convert_to_est(dt_utc)
	#     hrv_x.append(dt_est)
	#     hrv_y.append(hrv["value"])
	# ax2.plot(hrv_x, hrv_y, color='purple', label='HRV (ms)', linewidth=1.2)

	# -- Respiration (breaths per minute)
	# If your data is in "sleep_data.get('respirationData', [])" or similar
	# or possibly "sleep_data['sleepMovement']" has a breath rate? 
	# We'll assume 'sleepRespiration' or something
	# respiration_data = sleep_data.get("wellnessEpochRespirationDataDTOList", [])
	# resp_x = []
	# resp_y = []
	# for r in respiration_data:
	#     dt_utc = parse_gmt_millis(r["startTimeGMT"])
	#     dt_est = convert_to_est(dt_utc)
	#     resp_x.append(dt_est)
	#     resp_y.append(r["respirationValue"])  # assuming this is breaths/min
	# ax2.plot(resp_x, resp_y, color='blue', label='Resp (bpm)', linewidth=1.2)

	# Build lines legend
	# lines_legend = ax2.legend(loc='upper right')
	# Combine with stage legend
	# A trick is to add the lines legend to the existing stage legend (or keep separate).
	# We'll just keep them separate for clarity.

    plt.title("Overlaid Sleep Stages + HR + Possibly More")
    fig.tight_layout()
    plt.show()

########################################################
# 3) SUMMARY FUNCTION (with percentages)
########################################################

def get_sleep_summary(sleep_doc):
    """
    Returns a dict summary of key stats:
    - total sleep seconds
    - deep, core, rem, awake seconds
    - % of each
    """
    sleep_data = sleep_doc.get("sleep_data", {})
    dailySleepDTO = sleep_data.get("dailySleepDTO", {})

    total_sleep_s = dailySleepDTO.get("sleepTimeSeconds", 0)
    deep_s  = dailySleepDTO.get("deepSleepSeconds", 0)
    rem_s   = dailySleepDTO.get("remSleepSeconds", 0)
    core_s  = dailySleepDTO.get("lightSleepSeconds", 0)
    awake_s = dailySleepDTO.get("awakeSleepSeconds", 0)

    def pct(part, whole):
        return round(part / whole * 100, 1) if whole > 0 else 0

    summary = {
        "date": sleep_doc["date"],
        "total_sleep_seconds": total_sleep_s,
        "deep_sleep_seconds": deep_s,
        "core_sleep_seconds": core_s,
        "rem_sleep_seconds": rem_s,
        "awake_sleep_seconds": awake_s,
        "deep_pct": pct(deep_s, total_sleep_s),
        "core_pct": pct(core_s, total_sleep_s),
        "rem_pct": pct(rem_s, total_sleep_s),
        "awake_pct": pct(awake_s, total_sleep_s),
    }
    return summary

########################################################
# TEST / MAIN
########################################################

if __name__ == "__main__":
    client = MongoClient("mongodb://127.0.0.1:27017/")
    db = client["gymbro_db"]
    sleep_coll = db["garmin_sleep"]

    sleep_doc = sleep_coll.find_one(sort=[("date", -1)])
    # sleep_doc = sleep_coll.find().sort("date", -1).skip(3).limit(1).next()

    if not sleep_doc:
        print("No sleep docs found in DB.")
    else:
        # 1) Multi-subplots overview
        plot_sleep_overview(sleep_doc)

        # 2) Overlaid single plot with bars + lines
        plot_overlaid_sleep_stages_lines(sleep_doc)

        # 3) Summary
        summary_info = get_sleep_summary(sleep_doc)
        print("Sleep Summary:", summary_info)