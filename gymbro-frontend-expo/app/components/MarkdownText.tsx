import React from 'react';
import { Text, View, StyleSheet } from 'react-native';

interface MarkdownTextProps {
  content: string;
  style?: any;
}

export const MarkdownText: React.FC<MarkdownTextProps> = ({ content, style }) => {
  if (!content) return null;

  // Split into lines
  const lines = content.split('\n');

  return (
    <View style={styles.container}>
      {lines.map((line, lineIdx) => {
        const trimmed = line.trim();
        if (!trimmed) {
          return <View key={lineIdx} style={{ height: 6 }} />;
        }

        // Headings (e.g. ### Heading or ## Heading)
        if (trimmed.startsWith('#')) {
          const headingText = trimmed.replace(/^#+\s*/, '');
          return (
            <Text key={lineIdx} style={[styles.headingText, style]}>
              {renderFormattedInline(headingText)}
            </Text>
          );
        }

        // Bullet points (e.g. - Bullet or * Bullet)
        if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
          const bulletText = trimmed.substring(2);
          return (
            <View key={lineIdx} style={styles.bulletRow}>
              <Text style={styles.bulletDot}>•</Text>
              <Text style={[styles.bulletText, style]}>
                {renderFormattedInline(bulletText)}
              </Text>
            </View>
          );
        }

        // Standard Paragraph
        return (
          <Text key={lineIdx} style={[styles.paragraphText, style]}>
            {renderFormattedInline(line)}
          </Text>
        );
      })}
    </View>
  );
};

// Helper function to parse **bold** and *italic* inlines
const renderFormattedInline = (text: string) => {
  // Regex splitting on **bold** or *italic*
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g);

  return parts.map((part, idx) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      const boldStr = part.slice(2, -2);
      return (
        <Text key={idx} style={styles.boldText}>
          {boldStr}
        </Text>
      );
    }
    if (part.startsWith('*') && part.endsWith('*')) {
      const italicStr = part.slice(1, -1);
      return (
        <Text key={idx} style={styles.italicText}>
          {italicStr}
        </Text>
      );
    }
    return <Text key={idx}>{part}</Text>;
  });
};

const styles = StyleSheet.create({
  container: {
    width: '100%',
  },
  paragraphText: {
    color: '#F8FAFC',
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 4,
  },
  headingText: {
    color: '#00E5FF',
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
    color: '#10B981',
    fontSize: 16,
    marginRight: 8,
    lineHeight: 20,
  },
  bulletText: {
    color: '#F8FAFC',
    fontSize: 14,
    lineHeight: 20,
    flex: 1,
  },
  boldText: {
    fontWeight: 'bold',
    color: '#FFFFFF',
  },
  italicText: {
    fontStyle: 'italic',
    color: '#CBD5E1',
  },
});
