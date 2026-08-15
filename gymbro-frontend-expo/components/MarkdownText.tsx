import React from 'react';
import { Text, View, StyleSheet } from 'react-native';
import Colors from '../constants/Colors';

interface MarkdownTextProps {
  content: string;
  isUser?: boolean;
  textColor?: string;
  style?: any;
}

export const MarkdownText: React.FC<MarkdownTextProps> = ({ content, isUser = false, textColor: customTextColor, style }) => {
  if (!content) return null;

  const textColor = customTextColor || (isUser ? '#FFFFFF' : Colors.light.text);
  const headingColor = isUser ? '#FFFFFF' : Colors.light.primary;

  const lines = content.split('\n');

  return (
    <View style={styles.container}>
      {lines.map((line, lineIdx) => {
        const trimmed = line.trim();
        if (!trimmed) {
          return <View key={lineIdx} style={{ height: 6 }} />;
        }

        if (trimmed.startsWith('#')) {
          const headingText = trimmed.replace(/^#+\s*/, '');
          return (
            <Text key={lineIdx} style={[styles.headingText, { color: headingColor }, style]}>
              {renderFormattedInline(headingText, textColor)}
            </Text>
          );
        }

        if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
          const bulletText = trimmed.substring(2);
          return (
            <View key={lineIdx} style={styles.bulletRow}>
              <Text style={[styles.bulletDot, { color: isUser ? '#FFFFFF' : Colors.light.secondary }]}>•</Text>
              <Text style={[styles.bulletText, { color: textColor }, style]}>
                {renderFormattedInline(bulletText, textColor)}
              </Text>
            </View>
          );
        }

        return (
          <Text key={lineIdx} style={[styles.paragraphText, { color: textColor }, style]}>
            {renderFormattedInline(line, textColor)}
          </Text>
        );
      })}
    </View>
  );
};

const renderFormattedInline = (text: string, defaultColor: string) => {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g);

  return parts.map((part, idx) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      const boldStr = part.slice(2, -2);
      return (
        <Text key={idx} style={[styles.boldText, { color: defaultColor }]}>
          {boldStr}
        </Text>
      );
    }
    if (part.startsWith('*') && part.endsWith('*')) {
      const italicStr = part.slice(1, -1);
      return (
        <Text key={idx} style={[styles.italicText, { color: defaultColor }]}>
          {italicStr}
        </Text>
      );
    }
    return <Text key={idx} style={{ color: defaultColor }}>{part}</Text>;
  });
};

const styles = StyleSheet.create({
  container: {
    width: '100%',
  },
  paragraphText: {
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 4,
  },
  headingText: {
    fontSize: 16,
    fontWeight: 'bold',
    marginVertical: 6,
  },
  bulletRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginVertical: 2,
    paddingLeft: 4,
  },
  bulletDot: {
    fontSize: 16,
    marginRight: 8,
    lineHeight: 20,
  },
  bulletText: {
    fontSize: 14,
    lineHeight: 20,
    flex: 1,
  },
  boldText: {
    fontWeight: 'bold',
  },
  italicText: {
    fontStyle: 'italic',
  },
});
