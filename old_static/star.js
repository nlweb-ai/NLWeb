import React from 'react';
import { Star } from 'lucide-react';

const StarRating = ({ rating = 0, totalStars = 5, size = 16 }) => {
  // Ensure rating is a valid number between 0 and totalStars
  const validRating = Math.max(0, Math.min(Number(rating) || 0, totalStars));
  
  const fullStars = Math.floor(validRating);
  const hasHalfStar = validRating % 1 >= 0.5;
  const emptyStars = Math.max(0, totalStars - fullStars - (hasHalfStar ? 1 : 0));

  return (
    <div className="flex items-center">
      {/* Full stars */}
      {Array.from({ length: fullStars }, (_, i) => (
        <Star 
          key={`full-${i}`}
          size={size}
          className="text-yellow-400 fill-yellow-400"
        />
      ))}
      
      {/* Half star if needed */}
      {hasHalfStar && (
        <div className="relative">
          <Star 
            size={size}
            className="text-gray-300 fill-gray-300"
          />
          <div className="absolute top-0 left-0 overflow-hidden w-1/2">
            <Star 
              size={size}
              className="text-yellow-400 fill-yellow-400"
            />
          </div>
        </div>
      )}
      
      {/* Empty stars */}
      {Array.from({ length: emptyStars }, (_, i) => (
        <Star 
          key={`empty-${i}`}
          size={size}
          className="text-gray-300 fill-gray-300"
        />
      ))}
    </div>
  );
};

export default StarRating;

