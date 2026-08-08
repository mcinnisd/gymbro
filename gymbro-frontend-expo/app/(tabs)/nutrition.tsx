import React, { useState, useEffect, useContext } from 'react';
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
} from 'react-native';
import { AuthContext } from '../context/AuthContext';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import * as ImagePicker from 'expo-image-picker';

interface MealLog {
  id: number;
  meal_name: string;
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
  created_at: string;
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

export default function NutritionScreen() {
  const { authToken, apiUrl } = useContext(AuthContext);
  const [logs, setLogs] = useState<MealLog[]>([]);
  const [loading, setLoading] = useState(true);
  
  // Daily Totals & Targets
  const [totals, setTotals] = useState({ calories: 0, protein: 0, carbs: 0, fat: 0 });
  const [targets, setTargets] = useState({ calories: 2500, protein: 160, carbs: 250, fat: 70 });

  // Photo Logging Modal
  const [photoBase64, setPhotoBase64] = useState<string | null>(null);
  const [estimating, setEstimating] = useState(false);
  const [estimateData, setEstimateData] = useState<EstimateResult | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  
  // Custom manual logging or final modifications
  const [showLogModal, setShowLogModal] = useState(false);
  const [mealNameInput, setMealNameInput] = useState('');
  const [caloriesInput, setCaloriesInput] = useState('');
  const [proteinInput, setProteinInput] = useState('');
  const [carbsInput, setCarbsInput] = useState('');
  const [fatInput, setFatInput] = useState('');

  useEffect(() => {
    if (authToken) {
      fetchHistory();
    }
  }, [authToken]);

  const fetchHistory = async () => {
    setLoading(true);
    try {
      const today = new Date().toISOString().split('T')[0];
      const response = await fetch(`${apiUrl}/nutrition/history?start_date=${today}&end_date=${today}`, {
        method: 'GET',
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (response.ok) {
        const data = await response.json();
        setLogs(data.logs || []);
        
        // Sum totals
        const daySummary = data.daily_summaries?.[today] || { calories: 0, protein: 0, carbs: 0, fat: 0 };
        setTotals({
          calories: Math.round(daySummary.calories),
          protein: Math.round(daySummary.protein),
          carbs: Math.round(daySummary.carbs),
          fat: Math.round(daySummary.fat),
        });
      }
    } catch (err) {
      console.error('Error fetching nutrition history:', err);
    }
    setLoading(false);
  };

  const handlePickImage = async (useCamera: boolean) => {
    try {
      let result;
      if (useCamera) {
        const { status } = await ImagePicker.requestCameraPermissionsAsync();
        if (status !== 'granted') {
          Alert.alert('Permission Denied', 'Camera permission is required to scan your food.');
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
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({ image_base64: base64Str }),
      });
      if (response.ok) {
        const data = await response.json();
        const estCal = data.estimated_calories ?? data.calories ?? 0;
        const pG = data.protein_g ?? data.protein ?? 0;
        const cG = data.carbs_g ?? data.carbs ?? 0;
        const fG = data.fat_g ?? data.fat ?? 0;
        const name = data.meal_name || 'Logged Meal';

        setEstimateData({
          meal_name: name,
          estimated_ingredients: data.identified_ingredients || data.estimated_ingredients || [],
          calories: estCal,
          protein: pG,
          carbs: cG,
          fat: fG,
          confidence: data.confidence || 'high',
          clarifying_questions: data.clarifying_questions || []
        });
        
        // Populate inputs for adjustment form
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

  const handleSelectOption = (questionId: string, option: string) => {
    setAnswers((prev) => {
      const newAnswers = { ...prev, [questionId]: option };
      
      // Dynamic Adjustment logic based on answers!
      // E.g. if cooking oil is added, add ~120 kcal and 14g fat.
      // If portion size is double, multiply values by 2.
      let extraCal = 0;
      let extraFat = 0;
      let multiplier = 1;

      Object.entries(newAnswers).forEach(([qId, ans]) => {
        const ansLower = ans.toLowerCase();
        if (ansLower.includes('butter') || ansLower.includes('oil')) {
          extraCal += 120;
          extraFat += 14;
        }
        if (ansLower.includes('large') || ansLower.includes('double') || ansLower.includes('2x')) {
          multiplier = 1.8;
        }
        if (ansLower.includes('small') || ansLower.includes('half')) {
          multiplier = 0.6;
        }
      });

      if (estimateData) {
        setCaloriesInput(String(Math.round(estimateData.calories * multiplier + extraCal)));
        setProteinInput(String(Math.round(estimateData.protein * multiplier)));
        setCarbsInput(String(Math.round(estimateData.carbs * multiplier)));
        setFatInput(String(Math.round(estimateData.fat * multiplier + extraFat)));
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
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({
          meal_name: mealNameInput,
          calories: Number(caloriesInput),
          protein: Number(proteinInput),
          carbs: Number(carbsInput),
          fat: Number(fatInput),
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
    setMealNameInput('');
    setCaloriesInput('');
    setProteinInput('');
    setCarbsInput('');
    setFatInput('');
    setShowLogModal(true);
  };

  const calProgress = Math.min(totals.calories / targets.calories, 1);
  const proteinProgress = Math.min(totals.protein / targets.protein, 1);
  const carbsProgress = Math.min(totals.carbs / targets.carbs, 1);
  const fatProgress = Math.min(totals.fat / targets.fat, 1);

  return (
    <View style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {/* Calorie Ring Summary */}
        <View style={styles.calorieCard}>
          <LinearGradient
            colors={['rgba(108, 99, 255, 0.15)', 'rgba(0, 229, 255, 0.05)']}
            style={styles.gradientCard}
          >
            <View style={styles.headerRow}>
              <View>
                <Text style={styles.cardSubtitle}>TODAY'S CALORIES</Text>
                <Text style={styles.cardTitle}>
                  {totals.calories} <Text style={styles.cardTarget}>/ {targets.calories} kcal</Text>
                </Text>
              </View>
              <Ionicons name="flame" size={32} color="#EF4444" />
            </View>

            {/* Calorie Progress Bar */}
            <View style={styles.progressBarBg}>
              <View style={[styles.progressBarFill, { width: `${calProgress * 100}%`, backgroundColor: '#00E5FF' }]} />
            </View>
            <Text style={styles.pctLabel}>{Math.round(calProgress * 100)}% of Daily Goal</Text>
          </LinearGradient>
        </View>

        {/* Macros Summary Grid */}
        <View style={styles.macrosRow}>
          {/* Protein */}
          <View style={styles.macroCol}>
            <Text style={styles.macroName}>Protein</Text>
            <Text style={styles.macroVal}>
              {totals.protein}g<Text style={styles.macroTarget}> / {targets.protein}g</Text>
            </Text>
            <View style={styles.macroProgressBg}>
              <View style={[styles.macroProgressFill, { width: `${proteinProgress * 100}%`, backgroundColor: '#F97316' }]} />
            </View>
          </View>
          {/* Carbs */}
          <View style={styles.macroCol}>
            <Text style={styles.macroName}>Carbs</Text>
            <Text style={styles.macroVal}>
              {totals.carbs}g<Text style={styles.macroTarget}> / {targets.carbs}g</Text>
            </Text>
            <View style={styles.macroProgressBg}>
              <View style={[styles.macroProgressFill, { width: `${carbsProgress * 100}%`, backgroundColor: '#00E5FF' }]} />
            </View>
          </View>
          {/* Fat */}
          <View style={styles.macroCol}>
            <Text style={styles.macroName}>Fat</Text>
            <Text style={styles.macroVal}>
              {totals.fat}g<Text style={styles.macroTarget}> / {targets.fat}g</Text>
            </Text>
            <View style={styles.macroProgressBg}>
              <View style={[styles.macroProgressFill, { width: `${fatProgress * 100}%`, backgroundColor: '#FBBF24' }]} />
            </View>
          </View>
        </View>

        {/* Logging Options */}
        <View style={styles.actionsContainer}>
          <Text style={styles.sectionTitle}>Add Food Intake</Text>
          <View style={styles.actionButtonsRow}>
            <TouchableOpacity style={styles.scanBtn} onPress={() => handlePickImage(true)}>
              <LinearGradient colors={['#6C63FF', '#4F46E5']} style={styles.scanBtnGradient}>
                <Ionicons name="camera" size={20} color="#FFFFFF" />
                <Text style={styles.scanBtnText}>Scan Meal Photo</Text>
              </LinearGradient>
            </TouchableOpacity>

            <TouchableOpacity style={styles.manualBtn} onPress={openManualLog}>
              <Ionicons name="create-outline" size={20} color="#00E5FF" style={{ marginRight: 6 }} />
              <Text style={styles.manualBtnText}>Manual Log</Text>
            </TouchableOpacity>
          </View>
          
          <TouchableOpacity style={styles.galleryBtn} onPress={() => handlePickImage(false)}>
            <Ionicons name="images-outline" size={16} color="#94A3B8" style={{ marginRight: 6 }} />
            <Text style={styles.galleryBtnText}>Choose from Gallery</Text>
          </TouchableOpacity>
        </View>

        {/* Estimating Loader */}
        {estimating && (
          <View style={styles.loaderContainer}>
            <ActivityIndicator size="large" color="#00E5FF" />
            <Text style={styles.loaderText}>Gemini AI is analyzing your meal...</Text>
          </View>
        )}

        {/* Today's Logged Meals */}
        <View style={styles.mealsContainer}>
          <Text style={styles.sectionTitle}>Today's Logs</Text>
          {logs.length === 0 ? (
            <View style={styles.emptyMealsCard}>
              <Ionicons name="fast-food-outline" size={28} color="#00E5FF" style={{ marginBottom: 6 }} />
              <Text style={{ color: '#F8FAFC', fontWeight: 'bold', fontSize: 14 }}>No Meals Logged Today</Text>
              <Text style={{ color: '#94A3B8', fontSize: 12, textAlign: 'center', marginVertical: 6 }}>
                Snap a photo of your plate to instantly estimate calories, macros, and meal quality.
              </Text>
              <TouchableOpacity style={styles.emptyScanBtn} onPress={() => handlePickImage(true)}>
                <Ionicons name="camera" size={16} color="#FFFFFF" style={{ marginRight: 6 }} />
                <Text style={styles.emptyScanBtnText}>📸 Scan Meal Photo</Text>
              </TouchableOpacity>
            </View>
          ) : (
            logs.map((log) => (
              <View key={log.id} style={styles.mealItem}>
                <View style={styles.mealLeft}>
                  <View style={styles.mealBadge}>
                    <Ionicons name="restaurant-outline" size={16} color="#00E5FF" />
                  </View>
                  <View>
                    <Text style={styles.mealName}>{log.meal_name}</Text>
                    <Text style={styles.mealTime}>
                      {new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </Text>
                  </View>
                </View>
                <View style={styles.mealRight}>
                  <Text style={styles.mealCalories}>{Math.round(log.calories)} kcal</Text>
                  <Text style={styles.mealMacros}>
                    P: {Math.round(log.protein)}g • C: {Math.round(log.carbs)}g • F: {Math.round(log.fat)}g
                  </Text>
                </View>
              </View>
            ))
          )}
        </View>
      </ScrollView>

      {/* Estimations & Confirmation Modal */}
      <Modal
        visible={showLogModal}
        transparent
        animationType="slide"
        onRequestClose={() => setShowLogModal(false)}
      >
        <View style={styles.modalOverlay}>
          <ScrollView contentContainerStyle={styles.modalScroll}>
            <View style={styles.modalContent}>
              <View style={styles.modalHeaderRow}>
                <Text style={styles.modalTitle}>
                  {estimateData ? '🤖 AI Calorie Estimate' : 'Log Food Intake'}
                </Text>
                <TouchableOpacity onPress={() => setShowLogModal(false)}>
                  <Ionicons name="close" size={24} color="#94A3B8" />
                </TouchableOpacity>
              </View>

              {photoBase64 && (
                <Image source={{ uri: photoBase64 }} style={styles.foodPreview} />
              )}

              {/* Clarifying Questions Sheet */}
              {estimateData && estimateData.clarifying_questions && estimateData.clarifying_questions.length > 0 && (
                <View style={styles.questionsContainer}>
                  <Text style={styles.questionsTitle}>💡 Refine Estimate Details</Text>
                  <Text style={styles.questionsSubtitle}>To ensure absolute calorie accuracy, please clarify:</Text>
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
                              <Text style={[styles.optionText, isSelected && styles.optionTextSelected]}>{opt}</Text>
                            </TouchableOpacity>
                          );
                        })}
                      </View>
                    </View>
                  ))}
                </View>
              )}

              {/* Edit/Review Values */}
              <View style={styles.inputsForm}>
                <Text style={styles.formSectionTitle}>Verify Details</Text>
                
                <Text style={styles.inputLabel}>Meal Name</Text>
                <TextInput
                  style={styles.textInput}
                  value={mealNameInput}
                  onChangeText={setMealNameInput}
                  placeholder="Meal Name"
                  placeholderTextColor="#64748B"
                />

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
                    <Text style={styles.inputLabel}>Carbohydrates (g)</Text>
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
                    <Text style={[
                      styles.confidenceValue,
                      estimateData.confidence === 'high' && { color: '#10B981' },
                      estimateData.confidence === 'medium' && { color: '#F59E0B' },
                      estimateData.confidence === 'low' && { color: '#EF4444' },
                    ]}>
                      {estimateData.confidence.toUpperCase()}
                    </Text>
                  </View>
                )}
              </View>

              <TouchableOpacity style={styles.logSubmitBtn} onPress={handleLogMeal}>
                <Text style={styles.logSubmitText}>Log to Supabase</Text>
              </TouchableOpacity>
            </View>
          </ScrollView>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0A0E17',
  },
  scrollContent: {
    padding: 16,
    paddingBottom: 90, // space for drawer peek
  },
  calorieCard: {
    borderRadius: 16,
    overflow: 'hidden',
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#334155',
  },
  gradientCard: {
    padding: 20,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  cardSubtitle: {
    fontSize: 10,
    fontWeight: 'bold',
    color: '#94A3B8',
    letterSpacing: 1,
  },
  cardTitle: {
    fontSize: 28,
    fontWeight: '900',
    color: '#FFFFFF',
    marginTop: 4,
  },
  cardTarget: {
    fontSize: 14,
    fontWeight: 'normal',
    color: '#94A3B8',
  },
  progressBarBg: {
    height: 10,
    backgroundColor: '#1E293B',
    borderRadius: 5,
    overflow: 'hidden',
    marginVertical: 10,
  },
  progressBarFill: {
    height: '100%',
    borderRadius: 5,
  },
  pctLabel: {
    color: '#94A3B8',
    fontSize: 11,
    fontWeight: '600',
  },
  macrosRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 24,
  },
  macroCol: {
    flex: 1,
    backgroundColor: '#1E293B',
    borderRadius: 12,
    padding: 12,
    marginHorizontal: 4,
    borderWidth: 1,
    borderColor: '#334155',
  },
  macroName: {
    fontSize: 11,
    fontWeight: 'bold',
    color: '#94A3B8',
  },
  macroVal: {
    fontSize: 15,
    fontWeight: 'bold',
    color: '#F8FAFC',
    marginTop: 4,
  },
  macroTarget: {
    fontSize: 10,
    color: '#64748B',
    fontWeight: 'normal',
  },
  macroProgressBg: {
    height: 4,
    backgroundColor: '#0F172A',
    borderRadius: 2,
    marginTop: 8,
    overflow: 'hidden',
  },
  macroProgressFill: {
    height: '100%',
    borderRadius: 2,
  },
  actionsContainer: {
    backgroundColor: '#1E293B',
    borderRadius: 16,
    padding: 16,
    marginBottom: 24,
    borderWidth: 1,
    borderColor: '#334155',
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#F8FAFC',
    marginBottom: 12,
  },
  actionButtonsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  scanBtn: {
    flex: 1.2,
    borderRadius: 12,
    overflow: 'hidden',
    marginRight: 8,
  },
  scanBtnGradient: {
    height: 48,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  scanBtnText: {
    color: '#FFFFFF',
    fontWeight: 'bold',
    marginLeft: 8,
    fontSize: 14,
  },
  manualBtn: {
    flex: 1,
    height: 48,
    backgroundColor: 'rgba(0, 229, 255, 0.1)',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(0, 229, 255, 0.3)',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  manualBtnText: {
    color: '#00E5FF',
    fontWeight: 'bold',
    fontSize: 14,
  },
  galleryBtn: {
    flexDirection: 'row',
    alignSelf: 'center',
    alignItems: 'center',
    marginTop: 12,
    paddingVertical: 4,
  },
  galleryBtnText: {
    color: '#94A3B8',
    fontSize: 12,
    fontWeight: '600',
  },
  loaderContainer: {
    alignItems: 'center',
    marginVertical: 20,
  },
  loaderText: {
    color: '#00E5FF',
    fontSize: 13,
    fontWeight: '600',
    marginTop: 8,
  },
  mealsContainer: {
    marginBottom: 20,
  },
  emptyMealsText: {
    color: '#64748B',
    fontSize: 13,
    fontStyle: 'italic',
    paddingLeft: 4,
  },
  mealItem: {
    flexDirection: 'row',
    backgroundColor: '#1E293B',
    padding: 12,
    borderRadius: 12,
    marginBottom: 10,
    justifyContent: 'space-between',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#334155',
  },
  mealLeft: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  mealBadge: {
    width: 32,
    height: 32,
    borderRadius: 8,
    backgroundColor: 'rgba(0, 229, 255, 0.1)',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  mealName: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#F8FAFC',
  },
  mealTime: {
    fontSize: 11,
    color: '#64748B',
    marginTop: 2,
  },
  mealRight: {
    alignItems: 'flex-end',
  },
  mealCalories: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#EF4444',
  },
  mealMacros: {
    fontSize: 11,
    color: '#94A3B8',
    marginTop: 2,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'flex-end',
  },
  modalScroll: {
    flexGrow: 1,
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: '#0F172A',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    borderWidth: 1,
    borderColor: '#334155',
    padding: 20,
    maxHeight: '90%',
  },
  modalHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#F8FAFC',
  },
  foodPreview: {
    width: '100%',
    height: 160,
    borderRadius: 12,
    marginBottom: 16,
  },
  questionsContainer: {
    backgroundColor: '#1E293B',
    borderRadius: 12,
    padding: 12,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: 'rgba(0, 229, 255, 0.2)',
  },
  questionsTitle: {
    color: '#00E5FF',
    fontSize: 14,
    fontWeight: 'bold',
    marginBottom: 4,
  },
  questionsSubtitle: {
    fontSize: 11,
    color: '#94A3B8',
    marginBottom: 12,
  },
  questionBlock: {
    marginBottom: 12,
  },
  questionText: {
    color: '#F8FAFC',
    fontSize: 12,
    fontWeight: '600',
    marginBottom: 6,
  },
  optionsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  optionChip: {
    backgroundColor: '#0F172A',
    paddingHorizontal: 8,
    paddingVertical: 5,
    borderRadius: 8,
    marginRight: 6,
    marginBottom: 6,
    borderWidth: 1,
    borderColor: '#334155',
  },
  optionChipSelected: {
    backgroundColor: '#00E5FF',
    borderColor: '#00E5FF',
  },
  optionText: {
    color: '#94A3B8',
    fontSize: 11,
  },
  optionTextSelected: {
    color: '#020617',
    fontWeight: 'bold',
  },
  inputsForm: {
    backgroundColor: '#1E293B',
    borderRadius: 12,
    padding: 14,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#334155',
  },
  formSectionTitle: {
    fontSize: 13,
    fontWeight: 'bold',
    color: '#F8FAFC',
    marginBottom: 10,
  },
  inputLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: '#94A3B8',
    marginBottom: 4,
    marginTop: 6,
  },
  textInput: {
    backgroundColor: '#0F172A',
    borderWidth: 1,
    borderColor: '#334155',
    borderRadius: 8,
    height: 40,
    paddingHorizontal: 12,
    color: '#F8FAFC',
    fontSize: 14,
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
    marginTop: 12,
  },
  confidenceLabel: {
    fontSize: 11,
    color: '#64748B',
  },
  confidenceValue: {
    fontSize: 11,
    fontWeight: 'bold',
  },
  logSubmitBtn: {
    height: 48,
    backgroundColor: '#6C63FF',
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 20,
    marginBottom: 10,
  },
  logSubmitText: {
    color: '#FFFFFF',
    fontWeight: 'bold',
    fontSize: 15,
  },
  emptyMealsCard: {
    backgroundColor: '#1E293B',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#334155',
    padding: 20,
    alignItems: 'center',
    marginTop: 8,
  },
  emptyScanBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#6C63FF',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 8,
    marginTop: 8,
  },
  emptyScanBtnText: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: 'bold',
  },
});
