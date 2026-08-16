import React, { useState, useEffect, useContext, useMemo } from 'react';
import {
  StyleSheet,
  Text,
  View,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Modal,
  TextInput,
  Image,
  Alert,
  SafeAreaView,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { AuthContext } from '../../context/AuthContext';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import * as ImagePicker from 'expo-image-picker';
import Colors from '../../constants/Colors';

interface MealLog {
  id: number | string;
  meal_name: string;
  item_name?: string;
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
  date?: string;
  logged_at?: string;
  created_at?: string;
  quality_score?: number;
  coach_notes?: string;
}

interface ClarifyingQuestion {
  id: string;
  question: string;
  options: string[];
}

interface EstimateResult {
  meal_name: string;
  estimated_ingredients: string[];
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
  confidence: 'low' | 'medium' | 'high';
  clarifying_questions?: ClarifyingQuestion[];
}

interface DailyTarget {
  date: string;
  goal_type: string;
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  training_day: boolean;
  target_note: string;
}

export default function NutritionScreen() {
  const { authToken, apiUrl } = useContext(AuthContext);
  const [logs, setLogs] = useState<MealLog[]>([]);
  const [loading, setLoading] = useState(true);

  // Multi-day Date State
  const [selectedDate, setSelectedDate] = useState<string>(
    new Date().toISOString().split('T')[0]
  );
  const [dailySummaries, setDailySummaries] = useState<Record<string, any>>({});
  const [dailyTargets, setDailyTargets] = useState<Record<string, DailyTarget>>({});
  const [dailyAdherence, setDailyAdherence] = useState<Record<string, any>>({});
  const [periodAverages, setPeriodAverages] = useState<any>(null);
  const [coachSummary, setCoachSummary] = useState<string>('');

  // Photo Logging Modal
  const [photoBase64, setPhotoBase64] = useState<string | null>(null);
  const [estimating, setEstimating] = useState(false);
  const [estimateData, setEstimateData] = useState<EstimateResult | null>(null);
  const [baseValues, setBaseValues] = useState<{ calories: number; protein: number; carbs: number; fat: number } | null>(null);
  const [portionMultiplier, setPortionMultiplier] = useState<number>(1.0);
  const [answers, setAnswers] = useState<Record<string, string>>({});

  // Custom manual logging or final modifications
  const [showLogModal, setShowLogModal] = useState(false);
  const [mealNameInput, setMealNameInput] = useState('');
  const [caloriesInput, setCaloriesInput] = useState('');
  const [proteinInput, setProteinInput] = useState('');
  const [carbsInput, setCarbsInput] = useState('');
  const [fatInput, setFatInput] = useState('');
  const [recalculatingLog, setRecalculatingLog] = useState(false);

  // Barcode Scanner Modal
  const [showBarcodeModal, setShowBarcodeModal] = useState(false);
  const [barcodeInput, setBarcodeInput] = useState('');
  const [searchingBarcode, setSearchingBarcode] = useState(false);

  // Edit Existing Log Modal
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingLogId, setEditingLogId] = useState<number | string | null>(null);
  const [editItemName, setEditItemName] = useState('');
  const [editCalories, setEditCalories] = useState('');
  const [editProtein, setEditProtein] = useState('');
  const [editCarbs, setEditCarbs] = useState('');
  const [editFat, setEditFat] = useState('');
  const [updatingLog, setUpdatingLog] = useState(false);

  // Generate 7-day date window for date selector
  const dateList = useMemo(() => {
    const dates = [];
    const now = new Date();
    for (let i = 6; i >= 0; i--) {
      const d = new Date(now);
      d.setDate(d.getDate() - i);
      const iso = d.toISOString().split('T')[0];
      const dayName = i === 0 ? 'Today' : i === 1 ? 'Yday' : d.toLocaleDateString('en-US', { weekday: 'short' });
      const dayNum = d.getDate();
      dates.push({ iso, dayName, dayNum });
    }
    return dates;
  }, []);

  useEffect(() => {
    fetchHistory();
  }, [authToken]);

  const fetchHistory = async () => {
    setLoading(true);
    try {
      const today = new Date();
      const sevenDaysAgo = new Date();
      sevenDaysAgo.setDate(today.getDate() - 6);

      const startStr = sevenDaysAgo.toISOString().split('T')[0];
      const endStr = today.toISOString().split('T')[0];

      const response = await fetch(
        `${apiUrl}/nutrition/history?start_date=${startStr}&end_date=${endStr}`,
        {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${authToken || ''}`,
          },
        }
      );

      if (response.ok) {
        const data = await response.json();
        setLogs(data.logs || []);
        setDailySummaries(data.daily_summaries || {});
        setDailyTargets(data.daily_targets || {});
        setDailyAdherence(data.daily_adherence || {});
        setPeriodAverages(data.period_averages || null);
        setCoachSummary(data.coach_summary || '');
      }
    } catch (err) {
      console.error('Error fetching nutrition history:', err);
    }
    setLoading(false);
  };

  // Selected Day Totals & Targets
  const currentSummary = dailySummaries[selectedDate] || {
    calories: 0,
    protein: 0,
    carbs: 0,
    fat: 0,
  };
  const currentTarget: DailyTarget = dailyTargets[selectedDate] || {
    date: selectedDate,
    goal_type: 'Endurance Fueling',
    calories: 2500,
    protein_g: 160,
    carbs_g: 260,
    fat_g: 70,
    training_day: false,
    target_note: 'Daily baseline adaptive macro targets.',
  };
  const currentAdherence = dailyAdherence[selectedDate];

  const selectedDayLogs = logs.filter((l) => {
    const logD = l.date || (l.logged_at ? l.logged_at.slice(0, 10) : '') || (l.created_at ? l.created_at.slice(0, 10) : '');
    return logD === selectedDate;
  });

  const calProgress = Math.min(currentSummary.calories / Math.max(currentTarget.calories, 1), 1);
  const proteinProgress = Math.min(currentSummary.protein / Math.max(currentTarget.protein_g, 1), 1);
  const carbsProgress = Math.min(currentSummary.carbs / Math.max(currentTarget.carbs_g, 1), 1);
  const fatProgress = Math.min(currentSummary.fat / Math.max(currentTarget.fat_g, 1), 1);

  const openEditModal = (log: MealLog) => {
    setEditingLogId(log.id);
    setEditItemName(log.item_name || log.meal_name);
    setEditCalories(String(Math.round(log.calories)));
    setEditProtein(String(Math.round(log.protein)));
    setEditCarbs(String(Math.round(log.carbs)));
    setEditFat(String(Math.round(log.fat)));
    setShowEditModal(true);
  };

  const handleRecalculateMacrosFromInput = async (isEdit: boolean) => {
    const textToAnalyze = isEdit ? editItemName : mealNameInput;
    if (!textToAnalyze.trim()) return;

    setRecalculatingLog(true);
    try {
      const response = await fetch(`${apiUrl}/nutrition/reevaluate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken || ''}`,
        },
        body: JSON.stringify({ item_name: textToAnalyze }),
      });

      if (response.ok) {
        const data = await response.json();
        const cals = Math.round(data.calories);
        const p = Math.round(data.protein);
        const c = Math.round(data.carbs);
        const f = Math.round(data.fat);

        if (isEdit) {
          setEditCalories(String(cals));
          setEditProtein(String(p));
          setEditCarbs(String(c));
          setEditFat(String(f));
        } else {
          setBaseValues({ calories: cals, protein: p, carbs: c, fat: f });
          setPortionMultiplier(1.0);
          setCaloriesInput(String(cals));
          setProteinInput(String(p));
          setCarbsInput(String(c));
          setFatInput(String(f));
        }
      }
    } catch (err) {
      console.error('Error recalculating macros:', err);
    }
    setRecalculatingLog(false);
  };

  const applyPortionMultiplier = (multiplier: number) => {
    setPortionMultiplier(multiplier);
    const base = baseValues || {
      calories: Number(caloriesInput) || 500,
      protein: Number(proteinInput) || 30,
      carbs: Number(carbsInput) || 40,
      fat: Number(fatInput) || 15,
    };
    if (!baseValues) {
      setBaseValues(base);
    }
    setCaloriesInput(String(Math.round(base.calories * multiplier)));
    setProteinInput(String(Math.round(base.protein * multiplier)));
    setCarbsInput(String(Math.round(base.carbs * multiplier)));
    setFatInput(String(Math.round(base.fat * multiplier)));
  };

  const bumpCalories = (deltaKcal: number) => {
    const currentCal = Number(caloriesInput) || 0;
    const newCal = Math.max(0, currentCal + deltaKcal);
    const ratio = currentCal > 0 ? newCal / currentCal : 1.0;
    setCaloriesInput(String(newCal));
    setProteinInput(String(Math.max(0, Math.round((Number(proteinInput) || 0) * ratio))));
    setCarbsInput(String(Math.max(0, Math.round((Number(carbsInput) || 0) * ratio))));
    setFatInput(String(Math.max(0, Math.round((Number(fatInput) || 0) * ratio))));
  };

  const bumpPercentage = (deltaPct: number) => {
    const factor = 1.0 + deltaPct;
    setCaloriesInput(String(Math.max(0, Math.round((Number(caloriesInput) || 0) * factor))));
    setProteinInput(String(Math.max(0, Math.round((Number(proteinInput) || 0) * factor))));
    setCarbsInput(String(Math.max(0, Math.round((Number(carbsInput) || 0) * factor))));
    setFatInput(String(Math.max(0, Math.round((Number(fatInput) || 0) * factor))));
  };

  const handleUpdateLog = async () => {
    if (!editingLogId) return;
    setUpdatingLog(true);
    try {
      const response = await fetch(`${apiUrl}/nutrition/logs/${editingLogId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken || ''}`,
        },
        body: JSON.stringify({
          item_name: editItemName,
          calories: Number(editCalories),
          protein: Number(editProtein),
          carbs: Number(editCarbs),
          fat: Number(editFat),
        }),
      });

      if (response.ok) {
        setShowEditModal(false);
        setEditingLogId(null);
        fetchHistory();
        Alert.alert('Success', 'Meal log updated successfully!');
      } else {
        const err = await response.json();
        Alert.alert('Error', err.error || 'Failed to update log.');
      }
    } catch (err) {
      console.error('Error updating log:', err);
      Alert.alert('Error', 'Network error updating log.');
    }
    setUpdatingLog(false);
  };

  const handleDeleteLog = async (id: number | string) => {
    Alert.alert('Delete Log', 'Are you sure you want to delete this meal entry?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          try {
            const response = await fetch(`${apiUrl}/nutrition/logs/${id}`, {
              method: 'DELETE',
              headers: { Authorization: `Bearer ${authToken || ''}` },
            });
            if (response.ok) {
              fetchHistory();
            }
          } catch (err) {
            console.error('Error deleting log:', err);
          }
        },
      },
    ]);
  };

  const handlePickImage = async (useCamera: boolean) => {
    try {
      let result;
      if (useCamera) {
        const { status } = await ImagePicker.requestCameraPermissionsAsync();
        if (status !== 'granted') {
          Alert.alert('Permission Denied', 'Camera permission is required to scan meals.');
          return;
        }
        result = await ImagePicker.launchCameraAsync({
          mediaTypes: ImagePicker.MediaTypeOptions.Images,
          allowsEditing: true,
          aspect: [4, 3],
          quality: 0.8,
          base64: true,
        });
      } else {
        const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
        if (status !== 'granted') {
          Alert.alert('Permission Denied', 'Photo library permission is required to choose a meal photo.');
          return;
        }
        result = await ImagePicker.launchImageLibraryAsync({
          mediaTypes: ImagePicker.MediaTypeOptions.Images,
          allowsEditing: true,
          aspect: [4, 3],
          quality: 0.8,
          base64: true,
        });
      }

      if (!result.canceled && result.assets && result.assets[0].base64) {
        const base64Str = result.assets[0].base64;
        setPhotoBase64(result.assets[0].uri);
        estimateMeal(base64Str);
      }
    } catch (error) {
      console.error('Image picking error:', error);
      Alert.alert('Error', 'Failed to pick image.');
    }
  };

  const estimateMeal = async (base64Str: string) => {
    setEstimating(true);
    setEstimateData(null);
    setAnswers({});
    try {
      const response = await fetch(`${apiUrl}/nutrition/analyze-photo`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken || ''}`,
        },
        body: JSON.stringify({ image_base64: base64Str }),
      });
      if (response.ok) {
        const data = await response.json();
        const estCal = Math.round(data.estimated_calories ?? data.calories ?? 0);
        const pG = Math.round(data.protein_g ?? data.protein ?? 0);
        const cG = Math.round(data.carbs_g ?? data.carbs ?? 0);
        const fG = Math.round(data.fat_g ?? data.fat ?? 0);
        const name = data.meal_name || 'Logged Meal';

        setEstimateData({
          meal_name: name,
          estimated_ingredients: data.identified_ingredients || data.estimated_ingredients || [],
          calories: estCal,
          protein: pG,
          carbs: cG,
          fat: fG,
          confidence: data.confidence || 'high',
          clarifying_questions: data.clarifying_questions || [],
        });

        setBaseValues({ calories: estCal, protein: pG, carbs: cG, fat: fG });
        setPortionMultiplier(1.0);
        setMealNameInput(name);
        setCaloriesInput(String(estCal));
        setProteinInput(String(pG));
        setCarbsInput(String(cG));
        setFatInput(String(fG));

        setShowLogModal(true);
      } else {
        const err = await response.json();
        Alert.alert('Estimate Failed', err.error || 'Could not analyze image.');
      }
    } catch (err) {
      console.error('Error estimating meal nutrition:', err);
      Alert.alert('Error', 'Network error calling Gemini Nutrition Estimator.');
    }
    setEstimating(false);
  };

  const handleBarcodeLookup = async (codeToLookup: string) => {
    const code = codeToLookup.trim();
    if (!code) return;

    setSearchingBarcode(true);
    try {
      const response = await fetch(`${apiUrl}/nutrition/barcode/${code}`, {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${authToken || ''}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        const cals = Math.round(data.calories);
        const p = Math.round(data.protein || data.protein_g || 0);
        const c = Math.round(data.carbs || data.carbs_g || 0);
        const f = Math.round(data.fat || data.fat_g || 0);
        const name = data.meal_name || data.product_name || 'Scanned Product';

        setEstimateData(null);
        setPhotoBase64(null);
        setBaseValues({ calories: cals, protein: p, carbs: c, fat: f });
        setPortionMultiplier(1.0);
        setMealNameInput(name);
        setCaloriesInput(String(cals));
        setProteinInput(String(p));
        setCarbsInput(String(c));
        setFatInput(String(f));

        setShowBarcodeModal(false);
        setShowLogModal(true);
      } else {
        Alert.alert('Barcode Not Found', 'Could not locate product details for this barcode.');
      }
    } catch (err) {
      console.error('Error in barcode lookup:', err);
      Alert.alert('Error', 'Network error during barcode lookup.');
    }
    setSearchingBarcode(false);
  };

  const handleSelectOption = (questionId: string, option: string) => {
    setAnswers((prev) => {
      const newAnswers = { ...prev, [questionId]: option };

      let extraCal = 0;
      let extraFat = 0;
      let multiplier = 1.0;

      Object.entries(newAnswers).forEach(([_, ans]) => {
        const ansLower = ans.toLowerCase();
        if (ansLower.includes('butter') || ansLower.includes('oil')) {
          extraCal += 120;
          extraFat += 14;
        }
        if (ansLower.includes('large') || ansLower.includes('double') || ansLower.includes('2x')) {
          multiplier = 1.6;
        }
        if (ansLower.includes('small') || ansLower.includes('half')) {
          multiplier = 0.65;
        }
      });

      if (baseValues) {
        setCaloriesInput(String(Math.round(baseValues.calories * multiplier + extraCal)));
        setProteinInput(String(Math.round(baseValues.protein * multiplier)));
        setCarbsInput(String(Math.round(baseValues.carbs * multiplier)));
        setFatInput(String(Math.round(baseValues.fat * multiplier + extraFat)));
      }

      return newAnswers;
    });
  };

  const handleLogMeal = async () => {
    if (!mealNameInput.trim() || !caloriesInput || !proteinInput || !carbsInput || !fatInput) {
      Alert.alert('Missing Info', 'Please verify all inputs before saving.');
      return;
    }

    try {
      const response = await fetch(`${apiUrl}/nutrition/log`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken || ''}`,
        },
        body: JSON.stringify({
          meal_name: mealNameInput,
          calories: Number(caloriesInput),
          protein: Number(proteinInput),
          carbs: Number(carbsInput),
          fat: Number(fatInput),
          date: selectedDate,
        }),
      });

      if (response.ok) {
        setShowLogModal(false);
        setPhotoBase64(null);
        setEstimateData(null);
        fetchHistory();
        Alert.alert('Success', 'Meal logged successfully!');
      } else {
        const err = await response.json();
        Alert.alert('Failed', err.error || 'Failed to log meal.');
      }
    } catch (err) {
      console.error('Error logging meal:', err);
      Alert.alert('Error', 'Network error logging meal.');
    }
  };

  const openManualLog = () => {
    setPhotoBase64(null);
    setEstimateData(null);
    setBaseValues(null);
    setPortionMultiplier(1.0);
    setMealNameInput('');
    setCaloriesInput('');
    setProteinInput('');
    setCarbsInput('');
    setFatInput('');
    setShowLogModal(true);
  };

  return (
    <View style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {/* Date Selector Scroller */}
        <View style={styles.dateSelectorContainer}>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.dateScroll}>
            {dateList.map((d) => {
              const isSelected = d.iso === selectedDate;
              return (
                <TouchableOpacity
                  key={d.iso}
                  style={[styles.dateChip, isSelected && styles.dateChipSelected]}
                  onPress={() => setSelectedDate(d.iso)}
                >
                  <Text style={[styles.dateDayText, isSelected && styles.dateTextSelected]}>{d.dayName}</Text>
                  <Text style={[styles.dateNumText, isSelected && styles.dateTextSelected]}>{d.dayNum}</Text>
                </TouchableOpacity>
              );
            })}
          </ScrollView>
        </View>

        {/* Goal-Adaptive Target Banner */}
        <View style={styles.adaptiveTargetBanner}>
          <View style={styles.targetBannerLeft}>
            <View style={styles.targetBadgeRow}>
              <Ionicons
                name={currentTarget.training_day ? 'flash' : 'shield-checkmark'}
                size={16}
                color={currentTarget.training_day ? '#D97706' : '#2D6A4F'}
              />
              <Text style={styles.targetBadgeText}>
                {currentTarget.goal_type.toUpperCase()} TARGETS
              </Text>
            </View>
            <Text style={styles.targetNoteText}>{currentTarget.target_note}</Text>
          </View>
          {currentAdherence && (
            <View style={styles.adherenceBadge}>
              <Text style={styles.adherenceScore}>{Math.round(currentAdherence.overall_score || currentAdherence.score)}%</Text>
              <Text style={styles.adherenceLabel}>Adherence</Text>
            </View>
          )}
        </View>

        {/* Calorie Card Summary */}
        <View style={styles.calorieCard}>
          <LinearGradient
            colors={['#FFFFFF', '#FAF8F5']}
            style={styles.gradientCard}
          >
            <View style={styles.headerRow}>
              <View>
                <Text style={styles.cardSubtitle}>
                  {selectedDate === new Date().toISOString().split('T')[0] ? "TODAY'S CALORIES" : `${selectedDate} CALORIES`}
                </Text>
                <Text style={styles.cardTitle}>
                  {Math.round(currentSummary.calories)}{' '}
                  <Text style={styles.cardTarget}>/ {currentTarget.calories} kcal</Text>
                </Text>
              </View>
              <View style={styles.flameIconWrap}>
                <Ionicons name="flame" size={26} color="#E07A5F" />
              </View>
            </View>

            {/* Calorie Progress Bar */}
            <View style={styles.progressBarBg}>
              <View
                style={[
                  styles.progressBarFill,
                  { width: `${calProgress * 100}%`, backgroundColor: '#E07A5F' },
                ]}
              />
            </View>
            <View style={styles.calorieFooter}>
              <Text style={styles.pctLabel}>{Math.round(calProgress * 100)}% of Adaptive Target</Text>
              <Text style={styles.remainingLabel}>
                {Math.max(currentTarget.calories - Math.round(currentSummary.calories), 0)} kcal left
              </Text>
            </View>
          </LinearGradient>
        </View>

        {/* Macros Summary Grid */}
        <View style={styles.macrosRow}>
          {/* Protein */}
          <View style={styles.macroCol}>
            <Text style={styles.macroName}>Protein</Text>
            <Text style={styles.macroVal}>
              {Math.round(currentSummary.protein)}g
            </Text>
            <Text style={styles.macroTarget}>/ {currentTarget.protein_g}g</Text>
            <View style={styles.macroProgressBg}>
              <View
                style={[
                  styles.macroProgressFill,
                  { width: `${proteinProgress * 100}%`, backgroundColor: '#2D6A4F' },
                ]}
              />
            </View>
          </View>
          {/* Carbs */}
          <View style={styles.macroCol}>
            <Text style={styles.macroName}>Carbs</Text>
            <Text style={styles.macroVal}>
              {Math.round(currentSummary.carbs)}g
            </Text>
            <Text style={styles.macroTarget}>/ {currentTarget.carbs_g}g</Text>
            <View style={styles.macroProgressBg}>
              <View
                style={[
                  styles.macroProgressFill,
                  { width: `${carbsProgress * 100}%`, backgroundColor: '#D97706' },
                ]}
              />
            </View>
          </View>
          {/* Fat */}
          <View style={styles.macroCol}>
            <Text style={styles.macroName}>Fat</Text>
            <Text style={styles.macroVal}>
              {Math.round(currentSummary.fat)}g
            </Text>
            <Text style={styles.macroTarget}>/ {currentTarget.fat_g}g</Text>
            <View style={styles.macroProgressBg}>
              <View
                style={[
                  styles.macroProgressFill,
                  { width: `${fatProgress * 100}%`, backgroundColor: '#818CF8' },
                ]}
              />
            </View>
          </View>
        </View>

        {/* Action / Add Food Intake */}
        <View style={styles.actionsContainer}>
          <Text style={styles.sectionTitle}>Add Food Intake</Text>
          <View style={styles.actionButtonsRow}>
            <TouchableOpacity style={styles.scanBtn} onPress={() => handlePickImage(true)}>
              <View style={styles.scanBtnGradient}>
                <Ionicons name="camera" size={18} color="#FFFFFF" />
                <Text style={styles.scanBtnText}>Photo Scan</Text>
              </View>
            </TouchableOpacity>

            <TouchableOpacity style={styles.barcodeBtn} onPress={() => setShowBarcodeModal(true)}>
              <Ionicons name="barcode-outline" size={18} color="#2D6A4F" style={{ marginRight: 6 }} />
              <Text style={styles.barcodeBtnText}>Barcode</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.manualBtn} onPress={openManualLog}>
              <Ionicons name="create-outline" size={18} color={Colors.light.primary} style={{ marginRight: 6 }} />
              <Text style={styles.manualBtnText}>Manual</Text>
            </TouchableOpacity>
          </View>

          <TouchableOpacity style={styles.galleryBtn} onPress={() => handlePickImage(false)}>
            <Ionicons name="images-outline" size={15} color={Colors.light.mutedText} style={{ marginRight: 6 }} />
            <Text style={styles.galleryBtnText}>Choose from Gallery</Text>
          </TouchableOpacity>
        </View>

        {/* Estimating Loader */}
        {estimating && (
          <View style={styles.loaderContainer}>
            <ActivityIndicator size="large" color={Colors.light.primary} />
            <Text style={styles.loaderText}>Gemini AI is analyzing meal photo & portion geometry...</Text>
          </View>
        )}

        {/* Logged Meals List */}
        <View style={styles.mealsContainer}>
          <View style={styles.mealsHeaderRow}>
            <Text style={styles.sectionTitle}>
              {selectedDate === new Date().toISOString().split('T')[0] ? "Today's Logs" : `Logs for ${selectedDate}`}
            </Text>
            <Text style={styles.mealCountBadge}>{selectedDayLogs.length} Meals</Text>
          </View>

          {selectedDayLogs.length === 0 ? (
            <View style={styles.emptyMealsCard}>
              <Ionicons name="restaurant-outline" size={28} color={Colors.light.mutedText} style={{ marginBottom: 6 }} />
              <Text style={styles.emptyMealsTitle}>No Meals Logged for this Day</Text>
              <Text style={styles.emptyMealsSubtitle}>
                Snap a photo of your meal, scan a barcode, or manually enter items to track fuel and recovery.
              </Text>
              <View style={{ flexDirection: 'row', gap: 10 }}>
                <TouchableOpacity style={styles.emptyScanBtn} onPress={() => handlePickImage(true)}>
                  <Ionicons name="camera" size={16} color="#FFFFFF" style={{ marginRight: 6 }} />
                  <Text style={styles.emptyScanBtnText}>📸 Photo</Text>
                </TouchableOpacity>
                <TouchableOpacity style={[styles.emptyScanBtn, { backgroundColor: '#2D6A4F' }]} onPress={() => setShowBarcodeModal(true)}>
                  <Ionicons name="barcode-outline" size={16} color="#FFFFFF" style={{ marginRight: 6 }} />
                  <Text style={styles.emptyScanBtnText}>🔍 Barcode</Text>
                </TouchableOpacity>
              </View>
            </View>
          ) : (
            selectedDayLogs.map((log) => (
              <TouchableOpacity key={log.id} style={styles.mealItem} onPress={() => openEditModal(log)}>
                <View style={styles.mealLeft}>
                  <View style={styles.mealBadge}>
                    <Ionicons name="restaurant-outline" size={16} color={Colors.light.primary} />
                  </View>
                  <View style={{ flexShrink: 1, paddingRight: 8 }}>
                    <Text style={styles.mealName} numberOfLines={1}>
                      {log.item_name || log.meal_name}
                    </Text>
                    <Text style={styles.mealTime}>
                      {log.created_at
                        ? new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                        : 'Logged'}
                    </Text>
                  </View>
                </View>
                <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                  <View style={styles.mealRight}>
                    <Text style={styles.mealCalories}>{Math.round(log.calories)} kcal</Text>
                    <Text style={styles.mealMacros}>
                      P: {Math.round(log.protein)}g • C: {Math.round(log.carbs)}g • F: {Math.round(log.fat)}g
                    </Text>
                  </View>
                  <TouchableOpacity style={{ marginLeft: 8, padding: 4 }} onPress={() => openEditModal(log)}>
                    <Ionicons name="create-outline" size={18} color={Colors.light.primary} />
                  </TouchableOpacity>
                  <TouchableOpacity style={{ marginLeft: 4, padding: 4 }} onPress={() => handleDeleteLog(log.id)}>
                    <Ionicons name="trash-outline" size={18} color="#EF4444" />
                  </TouchableOpacity>
                </View>
              </TouchableOpacity>
            ))
          )}
        </View>
      </ScrollView>

      {/* Barcode Scanner / Lookup Modal */}
      <Modal
        visible={showBarcodeModal}
        transparent
        animationType="slide"
        onRequestClose={() => setShowBarcodeModal(false)}
      >
        <SafeAreaView style={styles.modalOverlay}>
          <View style={styles.barcodeModalContent}>
            <View style={styles.modalHeaderRow}>
              <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                <Ionicons name="barcode-outline" size={22} color="#2D6A4F" style={{ marginRight: 8 }} />
                <Text style={styles.modalTitle}>Scan / Enter Barcode</Text>
              </View>
              <TouchableOpacity onPress={() => setShowBarcodeModal(false)}>
                <Ionicons name="close" size={24} color={Colors.light.mutedText} />
              </TouchableOpacity>
            </View>

            <Text style={styles.barcodeHelpText}>
              Enter UPC/EAN barcode or select a common sports nutrition item:
            </Text>

            <View style={styles.barcodeInputRow}>
              <TextInput
                style={styles.barcodeTextInput}
                value={barcodeInput}
                onChangeText={setBarcodeInput}
                placeholder="e.g. 041570054771"
                placeholderTextColor="#94A3B8"
                keyboardType="numeric"
              />
              <TouchableOpacity
                style={styles.barcodeSearchBtn}
                onPress={() => handleBarcodeLookup(barcodeInput)}
                disabled={searchingBarcode || !barcodeInput.trim()}
              >
                {searchingBarcode ? (
                  <ActivityIndicator size="small" color="#FFFFFF" />
                ) : (
                  <Text style={styles.barcodeSearchBtnText}>Lookup</Text>
                )}
              </TouchableOpacity>
            </View>

            <Text style={styles.quickPresetsTitle}>⚡ Popular Sports Nutrition Barcodes</Text>
            <View style={styles.barcodeChipsWrap}>
              {[
                { name: 'Fairlife 42g Protein Shake', code: '041570054771' },
                { name: 'Quest Cookie Dough Bar', code: '888849000010' },
                { name: 'ON Gold Standard Whey', code: '748927028669' },
                { name: 'Chobani Plain Greek Yogurt', code: '894700010045' },
                { name: "Dave's 21 Whole Grains Bread", code: '073410013506' },
              ].map((item) => (
                <TouchableOpacity
                  key={item.code}
                  style={styles.barcodePresetChip}
                  onPress={() => {
                    setBarcodeInput(item.code);
                    handleBarcodeLookup(item.code);
                  }}
                >
                  <Ionicons name="flash-outline" size={12} color="#2D6A4F" style={{ marginRight: 4 }} />
                  <Text style={styles.barcodePresetChipText}>{item.name}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
        </SafeAreaView>
      </Modal>

      {/* Estimations & Confirmation Modal (Full Height Scrollable Sheet) */}
      <Modal
        visible={showLogModal}
        transparent
        animationType="slide"
        onRequestClose={() => setShowLogModal(false)}
      >
        <SafeAreaView style={styles.modalOverlay}>
          <KeyboardAvoidingView
            style={{ flex: 1 }}
            behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          >
            <View style={styles.modalContentFull}>
              {/* Header */}
              <View style={styles.modalHeaderRow}>
                <Text style={styles.modalTitle}>
                  {estimateData ? '🤖 AI Calorie Estimate' : 'Log Food Intake'}
                </Text>
                <TouchableOpacity onPress={() => setShowLogModal(false)}>
                  <Ionicons name="close" size={24} color={Colors.light.mutedText} />
                </TouchableOpacity>
              </View>

              <ScrollView
                style={{ flex: 1 }}
                contentContainerStyle={{ paddingBottom: 40 }}
                showsVerticalScrollIndicator={true}
                keyboardShouldPersistTaps="handled"
              >
                {photoBase64 && (
                  <Image source={{ uri: photoBase64 }} style={styles.foodPreview} />
                )}

                {/* Clarifying Questions Sheet */}
                {estimateData && estimateData.clarifying_questions && estimateData.clarifying_questions.length > 0 && (
                  <View style={styles.questionsContainer}>
                    <Text style={styles.questionsTitle}>💡 Refine Estimate Details</Text>
                    <Text style={styles.questionsSubtitle}>Tap to clarify cooking oils, sauces, or portions:</Text>
                    {estimateData.clarifying_questions.map((q) => (
                      <View key={q.id} style={styles.questionBlock}>
                        <Text style={styles.questionText}>{q.question}</Text>
                        <View style={styles.optionsRow}>
                          {q.options.map((opt) => {
                            const isSelected = answers[q.id] === opt;
                            return (
                              <TouchableOpacity
                                key={opt}
                                style={[styles.optionChip, isSelected && styles.optionChipSelected]}
                                onPress={() => handleSelectOption(q.id, opt)}
                              >
                                <Text style={[styles.optionText, isSelected && styles.optionTextSelected]}>
                                  {opt}
                                </Text>
                              </TouchableOpacity>
                            );
                          })}
                        </View>
                      </View>
                    ))}
                  </View>
                )}

                {/* Portion Scaling & Calorie Bump Controls */}
                <View style={styles.portionAdjustContainer}>
                  <Text style={styles.portionAdjustTitle}>⚡ Quick Portion & Calorie Scale</Text>
                  <Text style={styles.portionAdjustSubtitle}>Bump portion up/down to match your actual meal size:</Text>
                  
                  <View style={styles.multiplierRow}>
                    {[
                      { label: '0.75x', val: 0.75 },
                      { label: '1.0x', val: 1.0 },
                      { label: '1.25x', val: 1.25 },
                      { label: '1.5x', val: 1.5 },
                    ].map((m) => (
                      <TouchableOpacity
                        key={m.label}
                        style={[
                          styles.multiplierChip,
                          portionMultiplier === m.val && styles.multiplierChipActive,
                        ]}
                        onPress={() => applyPortionMultiplier(m.val)}
                      >
                        <Text
                          style={[
                            styles.multiplierText,
                            portionMultiplier === m.val && styles.multiplierTextActive,
                          ]}
                        >
                          {m.label}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>

                  <View style={styles.stepperRow}>
                    <TouchableOpacity style={styles.stepperBtn} onPress={() => bumpPercentage(-0.1)}>
                      <Text style={styles.stepperBtnText}>-10%</Text>
                    </TouchableOpacity>
                    <TouchableOpacity style={styles.stepperBtn} onPress={() => bumpCalories(-50)}>
                      <Text style={styles.stepperBtnText}>-50 kcal</Text>
                    </TouchableOpacity>
                    <TouchableOpacity style={styles.stepperBtn} onPress={() => bumpCalories(+50)}>
                      <Text style={styles.stepperBtnText}>+50 kcal</Text>
                    </TouchableOpacity>
                    <TouchableOpacity style={styles.stepperBtn} onPress={() => bumpPercentage(+0.1)}>
                      <Text style={styles.stepperBtnText}>+10%</Text>
                    </TouchableOpacity>
                  </View>
                </View>

                {/* Edit/Review Values */}
                <View style={styles.inputsForm}>
                  <Text style={styles.formSectionTitle}>Item Name & Portion</Text>
                  <TextInput
                    style={styles.textInput}
                    value={mealNameInput}
                    onChangeText={setMealNameInput}
                    placeholder="e.g. 200g Grilled Chicken Breast"
                    placeholderTextColor="#94A3B8"
                  />

                  <TouchableOpacity
                    style={styles.recalcButton}
                    onPress={() => handleRecalculateMacrosFromInput(false)}
                    disabled={recalculatingLog}
                  >
                    <Text style={styles.recalcButtonText}>
                      {recalculatingLog ? 'Recalculating...' : '⚡ Auto-Recalculate Macros from Description'}
                    </Text>
                  </TouchableOpacity>

                  <View style={styles.macroInputsRow}>
                    <View style={styles.macroInputWrapper}>
                      <Text style={styles.inputLabel}>Calories (kcal)</Text>
                      <TextInput
                        style={styles.textInput}
                        keyboardType="numeric"
                        value={caloriesInput}
                        onChangeText={setCaloriesInput}
                      />
                    </View>
                    <View style={styles.macroInputWrapper}>
                      <Text style={styles.inputLabel}>Protein (g)</Text>
                      <TextInput
                        style={styles.textInput}
                        keyboardType="numeric"
                        value={proteinInput}
                        onChangeText={setProteinInput}
                      />
                    </View>
                  </View>

                  <View style={styles.macroInputsRow}>
                    <View style={styles.macroInputWrapper}>
                      <Text style={styles.inputLabel}>Carbs (g)</Text>
                      <TextInput
                        style={styles.textInput}
                        keyboardType="numeric"
                        value={carbsInput}
                        onChangeText={setCarbsInput}
                      />
                    </View>
                    <View style={styles.macroInputWrapper}>
                      <Text style={styles.inputLabel}>Fat (g)</Text>
                      <TextInput
                        style={styles.textInput}
                        keyboardType="numeric"
                        value={fatInput}
                        onChangeText={setFatInput}
                      />
                    </View>
                  </View>

                  {estimateData && (
                    <View style={styles.confidenceRow}>
                      <Text style={styles.confidenceLabel}>Confidence: </Text>
                      <Text
                        style={[
                          styles.confidenceValue,
                          estimateData.confidence === 'high' && { color: '#10B981' },
                          estimateData.confidence === 'medium' && { color: '#F59E0B' },
                          estimateData.confidence === 'low' && { color: '#EF4444' },
                        ]}
                      >
                        {estimateData.confidence.toUpperCase()}
                      </Text>
                    </View>
                  )}
                </View>

                {/* Submit Action Button */}
                <TouchableOpacity style={styles.logSubmitBtn} onPress={handleLogMeal}>
                  <Text style={styles.logSubmitText}>Save Fueling Log</Text>
                </TouchableOpacity>
              </ScrollView>
            </View>
          </KeyboardAvoidingView>
        </SafeAreaView>
      </Modal>

      {/* Edit Existing Log Modal */}
      <Modal
        visible={showEditModal}
        transparent
        animationType="slide"
        onRequestClose={() => setShowEditModal(false)}
      >
        <SafeAreaView style={styles.modalOverlay}>
          <KeyboardAvoidingView
            style={{ flex: 1 }}
            behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          >
            <View style={styles.modalContentFull}>
              <View style={styles.modalHeaderRow}>
                <Text style={styles.modalTitle}>✏️ Edit Food Log</Text>
                <TouchableOpacity onPress={() => setShowEditModal(false)}>
                  <Ionicons name="close" size={24} color={Colors.light.mutedText} />
                </TouchableOpacity>
              </View>

              <ScrollView
                style={{ flex: 1 }}
                contentContainerStyle={{ paddingBottom: 40 }}
                showsVerticalScrollIndicator={true}
                keyboardShouldPersistTaps="handled"
              >
                <View style={styles.inputsForm}>
                  <Text style={styles.formSectionTitle}>Item Name & Quantity</Text>
                  <TextInput
                    style={styles.textInput}
                    value={editItemName}
                    onChangeText={setEditItemName}
                    placeholder="e.g. 200g Grilled Chicken Breast"
                    placeholderTextColor="#94A3B8"
                  />

                  <TouchableOpacity
                    style={styles.recalcButton}
                    onPress={() => handleRecalculateMacrosFromInput(true)}
                    disabled={updatingLog || recalculatingLog}
                  >
                    <Text style={styles.recalcButtonText}>
                      {recalculatingLog ? 'Recalculating...' : '⚡ Auto-Recalculate Macros from Description'}
                    </Text>
                  </TouchableOpacity>

                  <Text style={styles.formSectionTitle}>Macros</Text>
                  <View style={styles.macroInputsRow}>
                    <View style={styles.macroInputWrapper}>
                      <Text style={styles.inputLabel}>Calories (kcal)</Text>
                      <TextInput
                        style={styles.textInput}
                        keyboardType="numeric"
                        value={editCalories}
                        onChangeText={setEditCalories}
                      />
                    </View>
                    <View style={styles.macroInputWrapper}>
                      <Text style={styles.inputLabel}>Protein (g)</Text>
                      <TextInput
                        style={styles.textInput}
                        keyboardType="numeric"
                        value={editProtein}
                        onChangeText={setEditProtein}
                      />
                    </View>
                  </View>

                  <View style={styles.macroInputsRow}>
                    <View style={styles.macroInputWrapper}>
                      <Text style={styles.inputLabel}>Carbs (g)</Text>
                      <TextInput
                        style={styles.textInput}
                        keyboardType="numeric"
                        value={editCarbs}
                        onChangeText={setEditCarbs}
                      />
                    </View>
                    <View style={styles.macroInputWrapper}>
                      <Text style={styles.inputLabel}>Fat (g)</Text>
                      <TextInput
                        style={styles.textInput}
                        keyboardType="numeric"
                        value={editFat}
                        onChangeText={setEditFat}
                      />
                    </View>
                  </View>
                </View>

                <TouchableOpacity
                  style={styles.logSubmitBtn}
                  onPress={handleUpdateLog}
                  disabled={updatingLog}
                >
                  <Text style={styles.logSubmitText}>
                    {updatingLog ? 'Saving...' : 'Save & Re-evaluate Log'}
                  </Text>
                </TouchableOpacity>
              </ScrollView>
            </View>
          </KeyboardAvoidingView>
        </SafeAreaView>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.light.background,
  },
  scrollContent: {
    padding: 16,
    paddingBottom: 90,
  },
  dateSelectorContainer: {
    marginBottom: 14,
  },
  dateScroll: {
    paddingVertical: 4,
  },
  dateChip: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 12,
    backgroundColor: Colors.light.card,
    borderWidth: 1,
    borderColor: Colors.light.border,
    marginRight: 8,
    alignItems: 'center',
    minWidth: 54,
  },
  dateChipSelected: {
    backgroundColor: Colors.light.primary,
    borderColor: Colors.light.primary,
  },
  dateDayText: {
    fontSize: 11,
    fontWeight: '600',
    color: Colors.light.mutedText,
  },
  dateNumText: {
    fontSize: 15,
    fontWeight: 'bold',
    color: Colors.light.text,
    marginTop: 2,
  },
  dateTextSelected: {
    color: '#FFFFFF',
  },
  adaptiveTargetBanner: {
    flexDirection: 'row',
    backgroundColor: Colors.light.card,
    borderRadius: 14,
    padding: 14,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: Colors.light.border,
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  targetBannerLeft: {
    flex: 1,
    paddingRight: 10,
  },
  targetBadgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 4,
  },
  targetBadgeText: {
    fontSize: 11,
    fontWeight: '800',
    color: Colors.light.text,
    marginLeft: 6,
    letterSpacing: 0.5,
  },
  targetNoteText: {
    fontSize: 12,
    color: Colors.light.mutedText,
    lineHeight: 16,
  },
  adherenceBadge: {
    alignItems: 'center',
    backgroundColor: '#FAF5EE',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#E7DFD5',
  },
  adherenceScore: {
    fontSize: 16,
    fontWeight: '900',
    color: '#2D6A4F',
  },
  adherenceLabel: {
    fontSize: 9,
    fontWeight: '700',
    color: Colors.light.mutedText,
    textTransform: 'uppercase',
  },
  calorieCard: {
    borderRadius: 16,
    overflow: 'hidden',
    marginBottom: 16,
    borderWidth: 1,
    borderColor: Colors.light.border,
    backgroundColor: Colors.light.card,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 6,
    elevation: 2,
  },
  gradientCard: {
    padding: 18,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 14,
  },
  flameIconWrap: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: '#FDEEE9',
    alignItems: 'center',
    justifyContent: 'center',
  },
  cardSubtitle: {
    fontSize: 11,
    fontWeight: 'bold',
    color: Colors.light.mutedText,
    letterSpacing: 1,
  },
  cardTitle: {
    fontSize: 26,
    fontWeight: '900',
    color: Colors.light.text,
    marginTop: 4,
  },
  cardTarget: {
    fontSize: 14,
    fontWeight: 'normal',
    color: Colors.light.mutedText,
  },
  progressBarBg: {
    height: 10,
    backgroundColor: '#E7DFD5',
    borderRadius: 5,
    overflow: 'hidden',
    marginVertical: 8,
  },
  progressBarFill: {
    height: '100%',
    borderRadius: 5,
  },
  calorieFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 4,
  },
  pctLabel: {
    color: Colors.light.mutedText,
    fontSize: 11,
    fontWeight: '600',
  },
  remainingLabel: {
    color: Colors.light.text,
    fontSize: 11,
    fontWeight: '700',
  },
  macrosRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 20,
  },
  macroCol: {
    flex: 1,
    backgroundColor: Colors.light.card,
    borderRadius: 12,
    padding: 12,
    marginHorizontal: 3,
    borderWidth: 1,
    borderColor: Colors.light.border,
  },
  macroName: {
    fontSize: 11,
    fontWeight: 'bold',
    color: Colors.light.mutedText,
  },
  macroVal: {
    fontSize: 16,
    fontWeight: '900',
    color: Colors.light.text,
    marginTop: 3,
  },
  macroTarget: {
    fontSize: 10,
    color: Colors.light.mutedText,
    fontWeight: '500',
  },
  macroProgressBg: {
    height: 4,
    backgroundColor: '#E7DFD5',
    borderRadius: 2,
    marginTop: 8,
    overflow: 'hidden',
  },
  macroProgressFill: {
    height: '100%',
    borderRadius: 2,
  },
  actionsContainer: {
    backgroundColor: Colors.light.card,
    borderRadius: 16,
    padding: 16,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: Colors.light.border,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '800',
    color: Colors.light.text,
    marginBottom: 12,
  },
  actionButtonsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  scanBtn: {
    flex: 1.1,
    borderRadius: 12,
    overflow: 'hidden',
    marginRight: 6,
    backgroundColor: Colors.light.primary,
  },
  scanBtnGradient: {
    height: 46,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.light.primary,
  },
  scanBtnText: {
    color: '#FFFFFF',
    fontWeight: 'bold',
    marginLeft: 6,
    fontSize: 13,
  },
  barcodeBtn: {
    flex: 1.1,
    height: 46,
    backgroundColor: '#FAF5EE',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#2D6A4F',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 6,
  },
  barcodeBtnText: {
    color: '#2D6A4F',
    fontWeight: 'bold',
    fontSize: 13,
  },
  manualBtn: {
    flex: 1,
    height: 46,
    backgroundColor: '#FAF5EE',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: Colors.light.border,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  manualBtnText: {
    color: Colors.light.primary,
    fontWeight: 'bold',
    fontSize: 13,
  },
  galleryBtn: {
    flexDirection: 'row',
    alignSelf: 'center',
    alignItems: 'center',
    marginTop: 12,
    paddingVertical: 4,
  },
  galleryBtnText: {
    color: Colors.light.mutedText,
    fontSize: 12,
    fontWeight: '600',
  },
  loaderContainer: {
    alignItems: 'center',
    marginVertical: 18,
  },
  loaderText: {
    color: Colors.light.primary,
    fontSize: 12,
    fontWeight: '600',
    marginTop: 8,
  },
  mealsContainer: {
    marginBottom: 20,
  },
  mealsHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  mealCountBadge: {
    fontSize: 11,
    fontWeight: '700',
    color: Colors.light.mutedText,
  },
  emptyMealsCard: {
    backgroundColor: Colors.light.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: Colors.light.border,
    padding: 20,
    alignItems: 'center',
    marginTop: 4,
  },
  emptyMealsTitle: {
    color: Colors.light.text,
    fontWeight: 'bold',
    fontSize: 14,
    marginTop: 2,
  },
  emptyMealsSubtitle: {
    color: Colors.light.mutedText,
    fontSize: 12,
    textAlign: 'center',
    marginVertical: 6,
  },
  emptyScanBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.light.primary,
    paddingHorizontal: 14,
    paddingVertical: 9,
    borderRadius: 8,
    marginTop: 8,
  },
  emptyScanBtnText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: 'bold',
  },
  mealItem: {
    flexDirection: 'row',
    backgroundColor: Colors.light.card,
    padding: 12,
    borderRadius: 12,
    marginBottom: 9,
    justifyContent: 'space-between',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: Colors.light.border,
  },
  mealLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  mealBadge: {
    width: 32,
    height: 32,
    borderRadius: 8,
    backgroundColor: '#FAF5EE',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 10,
  },
  mealName: {
    fontSize: 13,
    fontWeight: 'bold',
    color: Colors.light.text,
  },
  mealTime: {
    fontSize: 11,
    color: Colors.light.mutedText,
    marginTop: 2,
  },
  mealRight: {
    alignItems: 'flex-end',
  },
  mealCalories: {
    fontSize: 13,
    fontWeight: 'bold',
    color: '#E07A5F',
  },
  mealMacros: {
    fontSize: 10,
    color: Colors.light.mutedText,
    marginTop: 2,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(15, 23, 42, 0.5)',
    justifyContent: 'flex-end',
  },
  modalContentFull: {
    flex: 1,
    backgroundColor: Colors.light.card,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    borderWidth: 1,
    borderColor: Colors.light.border,
    padding: 18,
    marginTop: 50,
  },
  modalHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  modalTitle: {
    fontSize: 17,
    fontWeight: 'bold',
    color: Colors.light.text,
  },
  foodPreview: {
    width: '100%',
    height: 140,
    borderRadius: 12,
    marginBottom: 12,
  },
  questionsContainer: {
    backgroundColor: '#FAF8F5',
    borderRadius: 12,
    padding: 12,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: Colors.light.border,
  },
  questionsTitle: {
    color: Colors.light.primary,
    fontSize: 13,
    fontWeight: 'bold',
    marginBottom: 2,
  },
  questionsSubtitle: {
    fontSize: 11,
    color: Colors.light.mutedText,
    marginBottom: 8,
  },
  questionBlock: {
    marginBottom: 10,
  },
  questionText: {
    color: Colors.light.text,
    fontSize: 12,
    fontWeight: '600',
    marginBottom: 6,
  },
  optionsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  optionChip: {
    backgroundColor: '#FFFFFF',
    paddingHorizontal: 8,
    paddingVertical: 5,
    borderRadius: 8,
    marginRight: 6,
    marginBottom: 6,
    borderWidth: 1,
    borderColor: Colors.light.border,
  },
  optionChipSelected: {
    backgroundColor: Colors.light.primary,
    borderColor: Colors.light.primary,
  },
  optionText: {
    color: Colors.light.mutedText,
    fontSize: 11,
  },
  optionTextSelected: {
    color: '#FFFFFF',
    fontWeight: 'bold',
  },
  portionAdjustContainer: {
    backgroundColor: '#FAF5EE',
    borderRadius: 12,
    padding: 12,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#E7DFD5',
  },
  portionAdjustTitle: {
    fontSize: 12,
    fontWeight: '800',
    color: Colors.light.text,
    marginBottom: 2,
  },
  portionAdjustSubtitle: {
    fontSize: 11,
    color: Colors.light.mutedText,
    marginBottom: 8,
  },
  multiplierRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  multiplierChip: {
    flex: 1,
    backgroundColor: '#FFFFFF',
    paddingVertical: 6,
    borderRadius: 8,
    marginHorizontal: 2,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#E7DFD5',
  },
  multiplierChipActive: {
    backgroundColor: Colors.light.primary,
    borderColor: Colors.light.primary,
  },
  multiplierText: {
    fontSize: 11,
    fontWeight: 'bold',
    color: Colors.light.mutedText,
  },
  multiplierTextActive: {
    color: '#FFFFFF',
  },
  stepperRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  stepperBtn: {
    flex: 1,
    backgroundColor: '#FFFFFF',
    paddingVertical: 6,
    borderRadius: 8,
    marginHorizontal: 2,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#E7DFD5',
  },
  stepperBtnText: {
    fontSize: 11,
    fontWeight: '700',
    color: Colors.light.text,
  },
  inputsForm: {
    backgroundColor: '#FAF8F5',
    borderRadius: 12,
    padding: 14,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: Colors.light.border,
  },
  formSectionTitle: {
    fontSize: 12,
    fontWeight: 'bold',
    color: Colors.light.text,
    marginBottom: 8,
  },
  recalcButton: {
    backgroundColor: '#FAF5EE',
    borderColor: '#E7DFD5',
    borderWidth: 1,
    borderRadius: 8,
    paddingVertical: 8,
    alignItems: 'center',
    marginTop: 8,
    marginBottom: 12,
  },
  recalcButtonText: {
    color: Colors.light.primary,
    fontWeight: 'bold',
    fontSize: 12,
  },
  inputLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: Colors.light.mutedText,
    marginBottom: 4,
    marginTop: 4,
  },
  textInput: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: Colors.light.border,
    borderRadius: 8,
    height: 38,
    paddingHorizontal: 10,
    color: Colors.light.text,
    fontSize: 13,
    width: '100%',
  },
  macroInputsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  macroInputWrapper: {
    flex: 1,
    marginRight: 8,
  },
  confidenceRow: {
    flexDirection: 'row',
    marginTop: 10,
  },
  confidenceLabel: {
    fontSize: 11,
    color: Colors.light.mutedText,
  },
  confidenceValue: {
    fontSize: 11,
    fontWeight: 'bold',
  },
  logSubmitBtn: {
    height: 48,
    backgroundColor: Colors.light.primary,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 8,
    marginBottom: 20,
  },
  logSubmitText: {
    color: '#FFFFFF',
    fontWeight: 'bold',
    fontSize: 14,
  },
  barcodeModalContent: {
    backgroundColor: Colors.light.card,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    borderWidth: 1,
    borderColor: Colors.light.border,
    padding: 20,
    maxHeight: '80%',
  },
  barcodeHelpText: {
    fontSize: 12,
    color: Colors.light.mutedText,
    marginBottom: 12,
  },
  barcodeInputRow: {
    flexDirection: 'row',
    marginBottom: 16,
  },
  barcodeTextInput: {
    flex: 1,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: Colors.light.border,
    borderRadius: 8,
    height: 42,
    paddingHorizontal: 12,
    color: Colors.light.text,
    fontSize: 14,
    marginRight: 8,
  },
  barcodeSearchBtn: {
    backgroundColor: '#2D6A4F',
    paddingHorizontal: 18,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  barcodeSearchBtnText: {
    color: '#FFFFFF',
    fontWeight: 'bold',
    fontSize: 13,
  },
  quickPresetsTitle: {
    fontSize: 12,
    fontWeight: '800',
    color: Colors.light.text,
    marginBottom: 8,
  },
  barcodeChipsWrap: {
    flexDirection: 'column',
  },
  barcodePresetChip: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FAF8F5',
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: Colors.light.border,
    marginBottom: 6,
  },
  barcodePresetChipText: {
    fontSize: 12,
    fontWeight: '600',
    color: Colors.light.text,
  },
});
